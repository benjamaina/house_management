"""Bank-statement parsing and tenant matching."""
import csv
import hashlib
import io
import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, time
from decimal import Decimal, InvalidOperation

from dateutil import parser as dateparser
from django.db import transaction
from django.db.models import DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rapidfuzz import fuzz

from tennants.models import (BankTransaction, LandlordProfile, Payment, PaymentAlias,
                             RentCharge, StatementUpload, Tenant)
from tennants.services.sms import TwilioNotificationService

logger = logging.getLogger(__name__)

AUTO_THRESHOLD = 80      # minimum score to auto-post
MIN_MARGIN = 25          # lead over the runner-up needed to auto-post
SUGGEST_THRESHOLD = 40   # minimum score to show as a suggestion


class StatementError(Exception):
    pass


class PasswordRequired(StatementError):
    pass


class NoAllocation(Exception):
    pass


# ============================================================================
# 1. PARSING
# ============================================================================

HEADER_SYNONYMS = {
    "date": ["completion time", "transaction date", "txn date", "value date", "posting date", "date"],
    "description": ["details", "description", "narration", "particulars", "transaction details", "remarks"],
    "reference": ["receipt no", "reference", "ref no", "ref", "transaction id", "transaction ref"],
    "credit": ["paid in", "credit", "credits", "money in", "deposit", "deposits"],
    "debit": ["withdrawn", "debit", "debits", "money out", "withdrawal", "withdrawals"],
    "amount": ["amount"],
    "type": ["dr cr", "drcr", "type", "transaction type"],
    "status": ["transaction status", "status"],
}

SOURCE_SIGNATURES = [
    ("mpesa", ("m-pesa", "mpesa", "safaricom")),
    ("equity", ("equity bank", "equity")),
    ("kcb", ("kcb", "kenya commercial bank")),
    ("coop", ("co-operative bank", "co-op bank", "cooperative bank", "co-operative")),
]

DATE_SHAPE = re.compile(r"\d{1,4}[-/ .]\w{1,9}[-/ .]\d{2,4}")


@dataclass
class ParsedRow:
    date: object
    description: str
    reference: str
    amount: Decimal
    raw: list = field(default_factory=list)


def detect_source(sample):
    low = sample.lower()
    for name, needles in SOURCE_SIGNATURES:
        if any(n in low for n in needles):
            return name
    return "generic"


def _clean_header(h):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z ]", " ", str(h or "").lower())).strip()


def map_columns(header):
    cleaned = [_clean_header(h) for h in header]
    mapping, used = {}, set()
    for exact in (True, False):               # exact header match first, then "contains"
        for fname, names in HEADER_SYNONYMS.items():
            if fname in mapping:
                continue
            for name in names:
                for i, h in enumerate(cleaned):
                    if i in used or not h:
                        continue
                    if (h == name) if exact else (name in h):
                        mapping[fname] = i
                        used.add(i)
                        break
                if fname in mapping:
                    break
    return mapping


def _is_header(m):
    return "date" in m and "description" in m and ("credit" in m or "amount" in m)


def parse_amount(value):
    s = str(value or "").strip()
    if not s:
        return None
    negative = s.startswith("-") or (s.startswith("(") and s.endswith(")"))
    s = re.sub(r"[^\d.]", "", re.sub(r"(?i)(kes|kshs|ksh)", "", s))
    if not s:
        return None
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    return -d if negative else d


def _cell(row, mapping, key):
    i = mapping.get(key)
    if i is None or i >= len(row) or row[i] is None:
        return ""
    return str(row[i]).strip()


def _parse_row(row, mapping):
    status = _cell(row, mapping, "status")
    if status and status.lower() not in ("completed", "complete", "success", "successful"):
        return None
    date_text = _cell(row, mapping, "date")
    if not DATE_SHAPE.search(date_text):       # skips totals, opening balance, repeated headers
        return None
    try:
        txn_date = dateparser.parse(date_text, dayfirst=True).date()
    except (ValueError, OverflowError):
        return None

    if "credit" in mapping:
        amount = parse_amount(_cell(row, mapping, "credit"))
    else:
        amount = parse_amount(_cell(row, mapping, "amount"))
        kind = _cell(row, mapping, "type").lower()
        if kind.startswith("d") or (amount is not None and amount < 0):
            amount = None
    if amount is None or amount <= 0:
        return None                            # debits / blanks are never ledger candidates

    return ParsedRow(txn_date, _cell(row, mapping, "description"),
                     _cell(row, mapping, "reference"), amount, [str(c) for c in row])


def rows_from_table(table):
    mapping, start = {}, None
    for i, row in enumerate(table[:40]):       # bank PDFs often have account info above the table
        m = map_columns(row)
        if _is_header(m):
            mapping, start = m, i
            break
    if start is None:
        return []
    out = []
    for row in table[start + 1:]:
        parsed = _parse_row(row, mapping)
        if parsed:
            out.append(parsed)
    return out


def read_csv(data):
    text = ""
    for enc in ("utf-8-sig", "latin-1"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    return list(csv.reader(io.StringIO(text), dialect)), text[:3000]


def read_pdf(data, password=None):
    try:
        import pdfplumber
    except ImportError:
        raise StatementError("PDF support is not installed on the server.")
    table, pages_text = [], []
    try:
        with pdfplumber.open(io.BytesIO(data), password=password or None) as pdf:
            for page in pdf.pages:
                pages_text.append(page.extract_text() or "")
                # ruled tables first; fall back to whitespace-aligned columns
                tables = page.extract_tables() or page.extract_tables(
                    {"vertical_strategy": "text", "horizontal_strategy": "text"})
                for t in tables:
                    table.extend([[(c or "").replace("\n", " ").strip() for c in r] for r in t])
    except Exception as e:
        if "password" in type(e).__name__.lower() or "password" in str(e).lower():
            raise PasswordRequired("PDF is password protected")
        raise StatementError(f"Could not read this PDF ({type(e).__name__}).")
    text = "\n".join(pages_text)
    if not text.strip():
        raise StatementError("This PDF is a scanned image with no readable text. "
                             "Download a text PDF or CSV from your bank instead.")
    return table, text[:3000]


def parse_statement(data, filename="", password=None):
    if data[:4] == b"%PDF":
        table, sample = read_pdf(data, password)
    elif filename.lower().endswith((".csv", ".txt")):
        table, sample = read_csv(data)
    else:
        raise StatementError("Unsupported file type. Upload a PDF or CSV statement.")
    rows = rows_from_table(table)
    if not rows:
        raise StatementError("No incoming payments found. The statement layout may not be "
                             "recognised yet. Try the bank's CSV export.")
    return detect_source(sample), rows


# ============================================================================
# 2. MATCHING
# ============================================================================

STOP = {
    "rent", "payment", "pay", "paid", "from", "funds", "fund", "received", "transfer", "mpesa",
    "pesa", "pesalink", "bank", "ltd", "deposit", "cash", "for", "the", "and", "mobile", "money",
    "ref", "acc", "account", "kes", "ksh", "being", "house", "hse", "unit", "apt", "flat", "month",
    "customer", "paybill", "till", "stk", "push", "eft", "rtgs", "cheque", "chq", "atm", "agent",
}

HOUSE_KEYWORD_RE = re.compile(
    r"\b(?:house|hse|hs|unit|apt|flat|room|rm|no)\.?\s*#?\s*([a-z]?\d{1,3}[a-z]?)\b", re.I)
HOUSE_CODE_RE = re.compile(r"\b([a-z]\d{1,3}|\d{1,3}[a-z])\b", re.I)   # B2, 4A (letter+digit only)


def _tokens(text):
    # \b...\b drops reference codes like QWE123XYZ (letters glued to digits)
    return [t for t in re.findall(r"\b[a-z]{3,}\b", str(text).lower()) if t not in STOP]


@dataclass
class TenantProfile:
    tenant: object
    name_tokens: list
    phone9: str
    house_no: str
    building_tokens: set
    rent: Decimal
    open_balances: set


@dataclass
class Context:
    profiles: list
    aliases: list                 # [(set_of_tokens, tenant_id)]
    by_house: dict


@dataclass
class Candidate:
    tenant: object
    score: int
    reasons: list


def open_charges(tenant=None, tenant_ids=None):
    """[(charge, balance)] for unpaid charges, oldest first. One query, no N+1."""
    qs = RentCharge.objects.all()
    qs = qs.filter(tenant=tenant) if tenant else qs.filter(tenant_id__in=tenant_ids)
    qs = (qs.annotate(paid=Coalesce(Sum("payments__amount"), Value(Decimal("0")),
                                    output_field=DecimalField(max_digits=12, decimal_places=2)))
            .filter(amount_due__gt=F("paid")).order_by("year", "month"))
    return [(c, c.amount_due - c.paid) for c in qs]


def build_context(user):
    tenants = list(Tenant.objects.filter(user=user, is_active=True, house__isnull=False)
                   .select_related("house__flat_building"))
    balances = defaultdict(set)
    for charge, bal in open_charges(tenant_ids=[t.pk for t in tenants]):
        balances[charge.tenant_id].add(bal)

    profiles, by_house = [], defaultdict(list)
    for t in tenants:
        p = TenantProfile(
            tenant=t, name_tokens=_tokens(t.full_name),
            phone9=re.sub(r"\D", "", str(t.phone))[-9:],
            house_no=t.house.house_number.upper(),
            building_tokens=set(_tokens(t.house.flat_building.building_name)),
            rent=t.house.house_rent_amount, open_balances=balances[t.pk],
        )
        profiles.append(p)
        by_house[p.house_no].append(p)
    aliases = [(set(a.alias.split()), a.tenant_id) for a in PaymentAlias.objects.filter(user=user)]
    return Context(profiles, aliases, by_house)


def _name_points(name_tokens, desc_tokens):
    if not name_tokens or not desc_tokens:
        return 0
    hits = sum(1 for nt in name_tokens if any(fuzz.ratio(nt, dt) >= 85 for dt in desc_tokens))
    if len(name_tokens) >= 2:
        return 45 if hits >= 2 else 20 if hits == 1 else 0
    return 25 if hits == 1 else 0


def _house_hits(text, tokset, ctx):
    codes = {m.upper() for m in HOUSE_KEYWORD_RE.findall(text)}
    codes |= {m.upper() for m in HOUSE_CODE_RE.findall(text)}
    hits = set()
    for code in codes:
        owners = ctx.by_house.get(code, [])
        if len(owners) > 1:                               # same number in several buildings
            owners = [p for p in owners if p.building_tokens & tokset]
        if len(owners) == 1:
            hits.add(owners[0].tenant.pk)
    return hits


def rank_tenants(description, reference, amount, ctx):
    text = f"{description} {reference}"
    tokset = set(_tokens(text))
    phones = {d[-9:] for d in re.findall(r"\d{9,13}", text)}
    house_hits = _house_hits(text, tokset, ctx)

    ranked = []
    for p in ctx.profiles:
        pts, why = 0, []
        if p.phone9 and p.phone9 in phones:
            pts += 80
            why.append("phone number")
        if any(tid == p.tenant.pk and a and a <= tokset for a, tid in ctx.aliases):
            pts += 80
            why.append("saved payer name")
        if p.tenant.pk in house_hits:
            pts += 50
            why.append(f"house {p.house_no}")
        name_pts = _name_points(p.name_tokens, tokset)
        if name_pts:
            pts += name_pts
            why.append("name")
        if pts and (amount == p.rent or amount in p.open_balances):   # never matches on amount alone
            pts += 20
            why.append("amount matches rent")
        if pts:
            ranked.append(Candidate(p.tenant, min(pts, 100), why))
    return sorted(ranked, key=lambda c: c.score, reverse=True)


# ============================================================================
# 3. POSTING TO THE LEDGER
# ============================================================================

def plan_allocation(tenant, amount):
    """Spread a payment over open charges, oldest first. Raise if it doesn't fit exactly."""
    remaining, plan = amount, []
    for charge, balance in open_charges(tenant=tenant):
        if remaining <= 0:
            break
        take = min(balance, remaining)
        plan.append((charge, take))
        remaining -= take
    if not plan:
        raise NoAllocation("This tenant has no unpaid rent charge. Create the charge first.")
    if remaining > 0:
        raise NoAllocation(f"Payment exceeds open charges by KES {remaining:,.2f}.")
    return plan


def _post(txn, tenant, plan):
    method = "mobile_money" if txn.upload.source == "mpesa" else "bank_transfer"
    paid_at = timezone.make_aware(datetime.combine(txn.txn_date, time(12, 0)))
    old = (timezone.localdate() - txn.txn_date).days > 3
    for charge, amount in plan:
        payment = Payment(
            user=txn.user, tenant=tenant, rent_charge=charge, amount=amount,
            payment_method=method, payment_reference=txn.reference or f"BT-{txn.pk}",
            paid_at=paid_at, bank_transaction=txn,
        )
        payment._skip_sms = old     # don't text tenants about months-old payments
        payment.save()


def attempt_auto(txn, ctx, allow_auto=True):
    ranked = rank_tenants(txn.description, txn.reference, txn.amount, ctx)
    txn.status, txn.tenant, txn.review_note = "review", None, ""
    txn.suggested_tenant, txn.confidence, txn.match_reason = None, 0, ""
    if not ranked:
        txn.review_note = "No tenant matched this payment."
        txn.save()
        return txn

    top = ranked[0]
    second = ranked[1] if len(ranked) > 1 else None
    if top.score >= SUGGEST_THRESHOLD:
        txn.suggested_tenant = top.tenant
        txn.confidence = top.score
        txn.match_reason = "Matched on " + ", ".join(top.reasons)

    if not allow_auto:
        txn.review_note = "Held for your confirmation (email import)."
    elif top.score < AUTO_THRESHOLD:
        txn.review_note = f"Not confident enough ({top.score}%)."
    elif second and top.score - second.score < MIN_MARGIN:
        txn.review_note = f"Could be {top.tenant.full_name} or {second.tenant.full_name}."
    else:
        try:
            with transaction.atomic():
                _post(txn, top.tenant, plan_allocation(top.tenant, txn.amount))
                txn.status, txn.tenant = "auto", top.tenant
                txn.resolved_at = timezone.now()
        except NoAllocation as e:
            txn.review_note = str(e)
        except Exception:
            logger.exception("Auto-post failed for transaction %s", txn.pk)
            txn.review_note = "Could not post automatically."
    txn.save()
    return txn


def assign_transaction(txn, tenant, save_alias=True):
    """Landlord resolves a Fix Queue item."""
    with transaction.atomic():
        if not open_charges(tenant=tenant):
            RentCharge.objects.get_or_create(
                tenant=tenant, year=txn.txn_date.year, month=txn.txn_date.month,
                defaults={"user": txn.user,
                          "amount_due": tenant.house.house_rent_amount if tenant.house else txn.amount},
            )
        _post(txn, tenant, plan_allocation(tenant, txn.amount))
        txn.status, txn.tenant, txn.review_note = "manual", tenant, ""
        txn.resolved_at = timezone.now()
        txn.save()
        if save_alias:
            toks = _tokens(txn.description)[:4]
            if len(toks) >= 2 or (toks and len(toks[0]) >= 6):   # too-generic aliases mis-match later
                PaymentAlias.objects.update_or_create(
                    user=txn.user, alias=" ".join(toks), defaults={"tenant": tenant})


def ignore_transaction(txn):
    txn.status, txn.resolved_at = "ignored", timezone.now()
    txn.save(update_fields=["status", "resolved_at"])


def rematch_pending(user):
    """Retry the Fix Queue (e.g. after new rent charges or aliases exist). Returns # auto-posted."""
    ctx = build_context(user)
    profile, _ = LandlordProfile.objects.get_or_create(user=user)
    posted = 0
    pending = BankTransaction.objects.filter(user=user, status="review").select_related("upload")
    for txn in pending:
        allow = txn.upload.channel == "upload" or profile.auto_approve_email
        attempt_auto(txn, ctx, allow_auto=allow)
        posted += txn.status == "auto"
    return posted


# ============================================================================
# 4. PIPELINE
# ============================================================================

def _fail(upload, message):
    upload.status, upload.error, upload.processed_at = "failed", message, timezone.now()
    upload.save()
    return upload


def _dedupe_keys(user, rows):
    seen, keys = Counter(), []
    for r in rows:
        desc = re.sub(r"\s+", " ", r.description.strip().lower())
        base = f"{user.pk}|{r.date}|{r.amount}|{r.reference.strip().upper()}|{desc}"
        seen[base] += 1      # 2 identical rows in one file are 2 payments; re-uploads reproduce the same keys
        keys.append(hashlib.sha256(f"{base}|{seen[base]}".encode()).hexdigest())
    return keys


def process_upload(upload, password=None, allow_auto=True):
    upload.status, upload.error = "processing", ""
    upload.save(update_fields=["status", "error"])
    try:
        with upload.file.open("rb") as fh:
            data = fh.read()
        source, rows = parse_statement(data, upload.original_name, password)
    except PasswordRequired:
        return _fail(upload, "This PDF is password protected. Upload it again with the password.")
    except StatementError as e:
        return _fail(upload, str(e))
    except Exception:
        logger.exception("Unexpected error parsing upload %s", upload.pk)
        return _fail(upload, "Unexpected error while reading the file.")

    keys = _dedupe_keys(upload.user, rows)
    existing = set(BankTransaction.objects.filter(user=upload.user, dedupe_key__in=keys)
                   .values_list("dedupe_key", flat=True))
    upload.source = source
    ctx = build_context(upload.user)
    duplicates = 0
    for row, key in zip(rows, keys):
        if key in existing:
            duplicates += 1
            continue
        txn = BankTransaction.objects.create(
            user=upload.user, upload=upload, txn_date=row.date, description=row.description,
            reference=row.reference[:60], amount=row.amount, dedupe_key=key, raw={"row": row.raw})
        attempt_auto(txn, ctx, allow_auto=allow_auto)

    upload.total_rows = len(rows)
    upload.duplicates = duplicates
    upload.auto_matched = upload.transactions.filter(status="auto").count()
    upload.needs_review = upload.transactions.filter(status="review").count()
    upload.status, upload.processed_at = "done", timezone.now()
    upload.save()
    notify_landlord(upload)
    return upload


def notify_landlord(upload):
    profile, _ = LandlordProfile.objects.get_or_create(user=upload.user)
    if not (profile.notify_sms and profile.phone) or not (upload.auto_matched + upload.needs_review):
        return
    msg = f"Statement processed: {upload.auto_matched} payment(s) reconciled automatically."
    if upload.needs_review:
        msg += f" {upload.needs_review} need your review."
    TwilioNotificationService().send_sms(profile.phone, msg)   # never raises; logs failures