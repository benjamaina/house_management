import hashlib
import hmac
import logging
import re
import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from tennants.forms import LandlordProfileForm
from tennants.models import BankTransaction, LandlordProfile, StatementUpload, Tenant
from tennants.services import reconcile as engine

logger = logging.getLogger(__name__)
MAX_BYTES = 10 * 1024 * 1024


def _ingest(user, name, data, channel, password=None, allow_auto=True):
    """Store + process one statement file. Returns (upload, problem_message)."""
    is_pdf = data[:4] == b"%PDF"
    if len(data) > MAX_BYTES:
        return None, f"{name}: larger than 10 MB."
    if not (is_pdf or name.lower().endswith((".csv", ".txt"))):
        return None, f"{name}: only PDF and CSV statements are supported."

    digest = hashlib.sha256(data).hexdigest()
    upload = StatementUpload.objects.filter(user=user, file_hash=digest).first()
    if upload and upload.status != "failed":
        return None, f"{name}: already uploaded on {upload.uploaded_at:%d %b %Y}."
    if upload is None:                       # a failed upload is retried in place (e.g. wrong password)
        upload = StatementUpload(user=user, file_hash=digest, original_name=name[:255], channel=channel)
        upload.file.save(digest[:16] + (".pdf" if is_pdf else ".csv"), ContentFile(data), save=False)
        upload.save()
    engine.process_upload(upload, password=password, allow_auto=allow_auto)
    return upload, None


@login_required
def statement_upload(request):
    if request.method == "POST":
        files = request.FILES.getlist("statements")
        password = request.POST.get("pdf_password") or None
        if not files:
            messages.error(request, "Choose at least one statement file.")
        any_review = False
        for f in files:
            upload, problem = _ingest(request.user, f.name, f.read(), "upload", password)
            if problem:
                messages.warning(request, problem)
            elif upload.status == "failed":
                messages.error(request, f"{f.name}: {upload.error}")
            else:
                any_review = any_review or upload.needs_review > 0
                messages.success(
                    request, f"{f.name}: {upload.auto_matched} reconciled, "
                             f"{upload.needs_review} need review, {upload.duplicates} already recorded.")
        return redirect("review_queue" if any_review else "statement_upload")

    profile, _ = LandlordProfile.objects.get_or_create(user=request.user)
    return render(request, "reconcile/upload.html", {
        "recent": StatementUpload.objects.filter(user=request.user)[:5],
        "forward_address": f"statements+{profile.inbound_token}@{settings.INBOUND_EMAIL_DOMAIN}",
    })


@login_required
def statement_list(request):
    uploads = StatementUpload.objects.filter(user=request.user)
    return render(request, "reconcile/statement_list.html",
                  {"page": Paginator(uploads, 25).get_page(request.GET.get("page"))})


@login_required
def review_queue(request):
    queue = (BankTransaction.objects.filter(user=request.user, status="review")
             .select_related("suggested_tenant__house__flat_building", "upload"))
    tenants = (Tenant.objects.filter(user=request.user, is_active=True)
               .select_related("house__flat_building").order_by("full_name"))
    return render(request, "reconcile/review_queue.html", {
        "page": Paginator(queue, 25).get_page(request.GET.get("page")),
        "tenants": tenants,
        "total": queue.count(),
    })


@login_required
@require_POST
def assign_transaction(request, pk):
    txn = get_object_or_404(BankTransaction, pk=pk, user=request.user, status="review")
    tenant = get_object_or_404(Tenant, pk=request.POST.get("tenant"), user=request.user)
    try:
        engine.assign_transaction(txn, tenant, save_alias=request.POST.get("remember") == "on")
        messages.success(request, f"KES {txn.amount:,.2f} assigned to {tenant.full_name}.")
    except engine.NoAllocation as e:
        messages.error(request, str(e))
    return redirect("review_queue")


@login_required
@require_POST
def ignore_transaction(request, pk):
    txn = get_object_or_404(BankTransaction, pk=pk, user=request.user, status="review")
    engine.ignore_transaction(txn)
    messages.info(request, "Transaction ignored.")
    return redirect("review_queue")


@login_required
@require_POST
def rematch(request):
    posted = engine.rematch_pending(request.user)
    messages.success(request, f"{posted} more payment(s) reconciled.")
    return redirect("review_queue")


@login_required
def reconcile_settings(request):
    profile, _ = LandlordProfile.objects.get_or_create(user=request.user)
    form = LandlordProfileForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Settings saved.")
        return redirect("reconcile_settings")
    return render(request, "reconcile/settings.html", {"form": form})


# ---------------------------------------------------------------------------
# Phase 2: inbound email (Mailgun "forward to URL" route shown; SendGrid Inbound
# Parse and Postmark differ only in field names and signature scheme).
# ---------------------------------------------------------------------------
@csrf_exempt
@require_POST
def inbound_email_webhook(request):
    key = getattr(settings, "MAILGUN_SIGNING_KEY", "")
    ts, token, sig = (request.POST.get(k, "") for k in ("timestamp", "token", "signature"))
    try:
        fresh = abs(time.time() - int(ts)) < 300
    except ValueError:
        fresh = False
    expected = hmac.new(key.encode(), f"{ts}{token}".encode(), hashlib.sha256).hexdigest()
    if not (key and fresh and hmac.compare_digest(expected, sig)):
        return HttpResponse(status=406)

    m = re.search(r"\+([0-9a-f]{16})@", request.POST.get("recipient", ""))
    profile = (LandlordProfile.objects.filter(inbound_token=m.group(1)).select_related("user").first()
               if m else None)
    if profile:     # unknown address: still answer 200 so we don't reveal which tokens exist
        for f in request.FILES.values():
            try:
                _ingest(profile.user, f.name, f.read(), "email", allow_auto=profile.auto_approve_email)
            except Exception:
                logger.exception("Inbound email attachment failed")
    return HttpResponse(status=200)