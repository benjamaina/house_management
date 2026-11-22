import hashlib
from tempfile import TemporaryDirectory
from decimal import Decimal
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from tennants.admin import FlatBuildingAdmin, HouseAdmin
from tennants.models import (
    BankTransaction,
    FlatBuilding,
    HistoryReport,
    House,
    Payment,
    PaymentAlias,
    RentCharge,
    StatementUpload,
    Tenant,
)
from tennants.services.reconcile import NoAllocation, assign_transaction, process_upload
from tennants.services.sms import TwilioNotificationService


class DashboardUnpaidChargesTests(TestCase):
    def test_dashboard_shows_only_owned_charges_with_positive_balances(self):
        owner = User.objects.create_user(username="owner", password="test-pass")
        other_owner = User.objects.create_user(username="other", password="test-pass")
        building = FlatBuilding.objects.create(
            user=owner, building_name="Owner building", address="One Street", number_of_houses=1
        )
        house = House.objects.create(
            user=owner, flat_building=building, house_number="1", house_rent_amount=1000
        )
        tenant = Tenant.objects.create(
            user=owner,
            full_name="Owner Tenant",
            email="owner-tenant@example.com",
            phone="+254712345678",
            id_number="1000000001",
            house=house,
            sms_notifications=False,
        )
        paid_charge = RentCharge.objects.create(
            user=owner, tenant=tenant, year=2025, month=1, amount_due=Decimal("1000.00")
        )
        unpaid_charge = RentCharge.objects.create(
            user=owner, tenant=tenant, year=2025, month=2, amount_due=Decimal("1000.00")
        )
        Payment.objects.create(
            user=owner, tenant=tenant, rent_charge=paid_charge,
            amount=Decimal("1000.00"), payment_method="cash",
        )
        Payment.objects.create(
            user=owner, tenant=tenant, rent_charge=unpaid_charge,
            amount=Decimal("400.00"), payment_method="cash",
        )

        other_building = FlatBuilding.objects.create(
            user=other_owner, building_name="Other building", address="Two Street", number_of_houses=1
        )
        other_house = House.objects.create(
            user=other_owner, flat_building=other_building, house_number="1", house_rent_amount=1000
        )
        other_tenant = Tenant.objects.create(
            user=other_owner,
            full_name="Other Tenant",
            email="other-tenant@example.com",
            phone="+254712345679",
            id_number="1000000002",
            house=other_house,
            sms_notifications=False,
        )
        RentCharge.objects.create(
            user=other_owner, tenant=other_tenant, year=2025, month=1,
            amount_due=Decimal("1000.00"),
        )

        self.client.force_login(owner)
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual([charge.pk for charge in response.context["unpaid_charges"]], [unpaid_charge.pk])
        self.assertContains(response, "Owner Tenant")
        self.assertNotContains(response, "Other Tenant")

    def test_payment_creates_one_ledger_snapshot_and_sends_sms_after_commit(self):
        user = User.objects.create_user(username="ledger-owner", password="test-pass")
        building = FlatBuilding.objects.create(
            user=user, building_name="Ledger building", address="One Street", number_of_houses=1
        )
        house = House.objects.create(
            user=user, flat_building=building, house_number="1", house_rent_amount=1000
        )
        tenant = Tenant.objects.create(
            user=user,
            full_name="Ledger Tenant",
            email="ledger-tenant@example.com",
            phone="+254712345680",
            id_number="1000000003",
            house=house,
            sms_notifications=False,
        )
        tenant.sms_notifications = True
        tenant.save(update_fields=["sms_notifications"])
        charge = RentCharge.objects.create(
            user=user, tenant=tenant, year=2025, month=1, amount_due=Decimal("1000.00")
        )

        with patch("tennants.signals.get_notification_service") as get_service:
            get_service.return_value.send_payment_confirmation.return_value = (True, "sent")
            with self.captureOnCommitCallbacks(execute=True):
                payment = Payment.objects.create(
                    user=user,
                    tenant=tenant,
                    rent_charge=charge,
                    amount=Decimal("250.00"),
                    payment_method="cash",
                )

        get_service.return_value.send_payment_confirmation.assert_called_once_with(payment)
        self.assertEqual(HistoryReport.objects.filter(payment=payment).count(), 1)
        self.assertEqual(HistoryReport.objects.get(payment=payment).balance_after, Decimal("750.00"))

    def test_statement_transaction_can_split_but_cannot_be_posted_twice(self):
        user = User.objects.create_user(username="reconcile-owner", password="test-pass")
        building = FlatBuilding.objects.create(
            user=user, building_name="Reconcile building", address="One Street", number_of_houses=1
        )
        house = House.objects.create(
            user=user, flat_building=building, house_number="1", house_rent_amount=1000
        )
        tenant = Tenant.objects.create(
            user=user,
            full_name="Reconcile Tenant",
            email="reconcile-tenant@example.com",
            phone="+254712345681",
            id_number="1000000004",
            house=house,
            sms_notifications=False,
        )
        first_charge = RentCharge.objects.create(
            user=user, tenant=tenant, year=2025, month=1, amount_due=Decimal("1000.00")
        )
        second_charge = RentCharge.objects.create(
            user=user, tenant=tenant, year=2025, month=2, amount_due=Decimal("1000.00")
        )
        upload = StatementUpload.objects.create(
            user=user, original_name="sample.csv", file_hash="a" * 64
        )
        txn = BankTransaction.objects.create(
            user=user,
            upload=upload,
            txn_date=timezone.localdate(),
            amount=Decimal("1500.00"),
            dedupe_key="b" * 64,
        )

        assign_transaction(txn, tenant, save_alias=False)

        posted = list(Payment.objects.filter(bank_transaction=txn).order_by("rent_charge__month"))
        self.assertEqual([payment.rent_charge_id for payment in posted], [
            first_charge.pk,
            second_charge.pk,
        ])
        self.assertEqual(sum((payment.amount for payment in posted), Decimal("0.00")), Decimal("1500.00"))
        with self.assertRaises(NoAllocation):
            assign_transaction(txn, tenant, save_alias=False)
        self.assertEqual(Payment.objects.filter(bank_transaction=txn).count(), 2)

    def test_reference_deduplication_is_scoped_to_owner_and_method(self):
        owners = [
            User.objects.create_user(username="reference-owner", password="test-pass"),
            User.objects.create_user(username="reference-other", password="test-pass"),
        ]
        tenants = []
        charges = []
        for index, owner in enumerate(owners):
            building = FlatBuilding.objects.create(
                user=owner, building_name=f"Reference building {index}",
                address="One Street", number_of_houses=1,
            )
            house = House.objects.create(
                user=owner, flat_building=building, house_number="1", house_rent_amount=1000
            )
            tenant = Tenant.objects.create(
                user=owner,
                full_name=f"Reference Tenant {index}",
                email=f"reference-{index}@example.com",
                phone=f"+25471234568{index}",
                id_number=f"100000001{index}",
                house=house,
                sms_notifications=False,
            )
            tenants.append(tenant)
            charges.append(RentCharge.objects.create(
                user=owner, tenant=tenant, year=2025, month=1, amount_due=Decimal("1000.00")
            ))

        Payment.objects.create(
            user=owners[0], tenant=tenants[0], rent_charge=charges[0],
            amount=Decimal("100.00"), payment_method="mobile_money",
            payment_reference=" MPESA-123 ",
        )
        with self.assertRaises(ValidationError):
            Payment.objects.create(
                user=owners[0], tenant=tenants[0], rent_charge=charges[0],
                amount=Decimal("100.00"), payment_method="mobile_money",
                payment_reference="mpesa-123",
            )
        Payment.objects.create(
            user=owners[0], tenant=tenants[0], rent_charge=charges[0],
            amount=Decimal("100.00"), payment_method="bank_transfer",
            payment_reference="mpesa-123",
        )
        Payment.objects.create(
            user=owners[1], tenant=tenants[1], rent_charge=charges[1],
            amount=Decimal("100.00"), payment_method="mobile_money",
            payment_reference="mpesa-123",
        )

    def test_overpayment_is_presented_as_credit_in_ui_and_sms(self):
        user = User.objects.create_user(username="credit-owner", password="test-pass")
        building = FlatBuilding.objects.create(
            user=user, building_name="Credit building", address="One Street", number_of_houses=1
        )
        house = House.objects.create(
            user=user, flat_building=building, house_number="1", house_rent_amount=1000
        )
        tenant = Tenant.objects.create(
            user=user,
            full_name="Credit Tenant",
            email="credit-tenant@example.com",
            phone="+254712345682",
            id_number="1000000012",
            house=house,
            sms_notifications=False,
        )
        charge = RentCharge.objects.create(
            user=user, tenant=tenant, year=2025, month=1, amount_due=Decimal("1000.00")
        )
        payment = Payment.objects.create(
            user=user, tenant=tenant, rent_charge=charge,
            amount=Decimal("1200.00"), payment_method="cash",
        )

        self.client.force_login(user)
        response = self.client.get(reverse("rent_charge_detail", args=[charge.pk]))
        message = TwilioNotificationService()._generate_payment_confirmation(payment)

        self.assertContains(response, "Credit: KES 200.00")
        self.assertContains(response, "Credit")
        self.assertIn("Credit balance: KES 200.00", message)
        self.assertNotIn("KES -200.00", message)

    def test_staff_admin_querysets_and_relation_choices_are_owner_scoped(self):
        owner = User.objects.create_user(username="admin-owner", password="test-pass", is_staff=True)
        other_owner = User.objects.create_user(
            username="admin-other", password="test-pass", is_staff=True
        )
        building = FlatBuilding.objects.create(
            user=owner, building_name="Admin owner building", address="One Street", number_of_houses=1
        )
        FlatBuilding.objects.create(
            user=other_owner, building_name="Admin other building", address="Two Street", number_of_houses=1
        )
        request = RequestFactory().get("/admin/")
        request.user = owner

        buildings = FlatBuildingAdmin(FlatBuilding, admin.site).get_queryset(request)
        building_field = HouseAdmin(House, admin.site).formfield_for_foreignkey(
            House._meta.get_field("flat_building"), request
        )

        self.assertEqual(list(buildings.values_list("pk", flat=True)), [building.pk])
        self.assertEqual(
            list(building_field.queryset.values_list("pk", flat=True)),
            [building.pk],
        )

    def test_api_cannot_read_or_charge_another_owners_records(self):
        owner = User.objects.create_user(username="api-owner", password="test-pass")
        other_owner = User.objects.create_user(username="api-other", password="test-pass")
        tenants_and_charges = []
        for index, user in enumerate((owner, other_owner)):
            building = FlatBuilding.objects.create(
                user=user, building_name=f"API building {index}",
                address="One Street", number_of_houses=1,
            )
            house = House.objects.create(
                user=user, flat_building=building, house_number="1", house_rent_amount=1000
            )
            tenant = Tenant.objects.create(
                user=user,
                full_name=f"API Tenant {index}",
                email=f"api-{index}@example.com",
                phone=f"+25471234569{index}",
                id_number=f"100000002{index}",
                house=house,
                sms_notifications=False,
            )
            charge = RentCharge.objects.create(
                user=user, tenant=tenant, year=2025, month=1, amount_due=Decimal("1000.00")
            )
            tenants_and_charges.append((tenant, charge))

        client = APIClient()
        client.force_authenticate(user=owner)
        other_tenant, other_charge = tenants_and_charges[1]
        self.assertEqual(
            client.get(reverse("tenant-detail", args=[other_tenant.pk])).status_code,
            404,
        )
        response = client.post(
            reverse("payment-list"),
            {
                "tenant": tenants_and_charges[0][0].pk,
                "rent_charge": other_charge.pk,
                "amount": "100.00",
                "payment_method": "cash",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_statement_reupload_dedupes_row_and_manual_assignment_remembers_alias(self):
        user = User.objects.create_user(username="upload-owner", password="test-pass")
        building = FlatBuilding.objects.create(
            user=user, building_name="Upload building", address="One Street", number_of_houses=1
        )
        house = House.objects.create(
            user=user, flat_building=building, house_number="1", house_rent_amount=1000
        )
        tenant = Tenant.objects.create(
            user=user,
            full_name="John Doe",
            email="upload-tenant@example.com",
            phone="+254712345683",
            id_number="1000000013",
            house=house,
            sms_notifications=False,
        )
        RentCharge.objects.create(
            user=user, tenant=tenant, year=2025, month=3, amount_due=Decimal("1000.00")
        )
        original = b"Date,Description,Reference,Credit\n2025-03-01,JOHN DOE rent,REF123,500\n"
        duplicate = original + b"\n"

        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            first = StatementUpload.objects.create(
                user=user,
                file=SimpleUploadedFile("first.csv", original, content_type="text/csv"),
                original_name="first.csv",
                file_hash=hashlib.sha256(original).hexdigest(),
            )
            process_upload(first, allow_auto=False)
            txn = BankTransaction.objects.get(upload=first)
            assign_transaction(txn, tenant, save_alias=True)

            second = StatementUpload.objects.create(
                user=user,
                file=SimpleUploadedFile("second.csv", duplicate, content_type="text/csv"),
                original_name="second.csv",
                file_hash=hashlib.sha256(duplicate).hexdigest(),
            )
            process_upload(second, allow_auto=False)
            second.refresh_from_db()

        self.assertEqual(second.duplicates, 1)
        self.assertEqual(BankTransaction.objects.filter(user=user).count(), 1)
        self.assertEqual(
            PaymentAlias.objects.get(user=user, alias="john doe").tenant_id,
            tenant.pk,
        )
