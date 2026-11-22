from datetime import timedelta
from urllib.parse import urlsplit
from unittest.mock import patch

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="RentFlow <no-reply@example.com>",
    SECURE_SSL_REDIRECT=False,
)
class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="propertyowner",
            email="owner@example.com",
            password="Original!Password928",
        )

    def test_password_reset_page_loads_and_login_links_to_it(self):
        response = self.client.get(reverse("password_reset"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reset your password")
        self.assertContains(self.client.get(reverse("login")), reverse("password_reset"))

    def test_registered_email_sends_reset_message(self):
        response = self.client.post(
            reverse("password_reset"),
            {"email": self.user.email},
            secure=True,
        )

        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        self.assertIn("https://testserver/acounts/reset/", mail.outbox[0].body)
        self.assertEqual(len(mail.outbox[0].alternatives), 1)
        html_body, content_type = mail.outbox[0].alternatives[0]
        self.assertEqual(content_type, "text/html")
        self.assertIn("Choose a new password", html_body)
        self.assertIn("https://testserver/acounts/reset/", html_body)

    def test_unknown_email_receives_same_confirmation_without_sending_email(self):
        response = self.client.post(
            reverse("password_reset"),
            {"email": "unknown@example.com"},
        )

        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(mail.outbox, [])
        self.assertContains(
            self.client.get(response.url),
            "If an active account with a usable password matches that email address",
        )

    def test_valid_reset_token_changes_password_and_allows_login(self):
        self.client.post(reverse("password_reset"), {"email": self.user.email})
        reset_url = next(
            line for line in mail.outbox[0].body.splitlines()
            if "/acounts/reset/" in line
        )
        response = self.client.get(urlsplit(reset_url).path, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose a new password")
        response = self.client.post(
            response.request["PATH_INFO"],
            {
                "new_password1": "New-RentFlow!Password928",
                "new_password2": "New-RentFlow!Password928",
            },
        )

        self.assertRedirects(response, reverse("password_reset_complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("New-RentFlow!Password928"))
        self.assertEqual(
            authenticate(username=self.user.username, password="New-RentFlow!Password928"),
            self.user,
        )

    def test_invalid_or_expired_token_is_rejected(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        invalid_url = reverse(
            "password_reset_confirm",
            kwargs={"uidb64": uid, "token": "invalid-token"},
        )
        invalid_response = self.client.get(invalid_url)
        self.assertContains(invalid_response, "This password reset link is invalid or has expired.")

        old_time = default_token_generator._now() - timedelta(days=2)
        with patch.object(default_token_generator, "_now", return_value=old_time):
            expired_token = default_token_generator.make_token(self.user)
        expired_url = reverse(
            "password_reset_confirm",
            kwargs={"uidb64": uid, "token": expired_token},
        )
        with override_settings(PASSWORD_RESET_TIMEOUT=timedelta(days=1).total_seconds()):
            expired_response = self.client.get(expired_url)

        self.assertContains(expired_response, "This password reset link is invalid or has expired.")

    def test_existing_login_still_works(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.user.username, "password": "Original!Password928"},
        )

        self.assertRedirects(response, "/dashboard/")
        self.assertTrue(response.wsgi_request.user.is_authenticated)
