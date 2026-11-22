"""
Read-only reporting queries behind the metrics and history pages.
No request/https code in here, so it is easy to test. Everything is scoped to one
landlord (`user`), and the date maths avoids `__date` / `__year` lookups on
datetimes (those need MySQL timezone tables when TIME_ZONE isn't UTC).
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, F, Prefetch, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from tennants.models import FlatBuilding, House, Payment, RentCharge, Tenant

ZERO = Decimal("0")
MONEY = DecimalField(max_digits=14, decimal_places=2)
RING_CIRCUMFERENCE = 301.6        # 2 * pi * 48, the radius used by _card_collection_ring.html

# Overdue buckets. Labels must match the colours hard-coded in the templates.
BUCKET_LABELS = ["0-30", "31-60", "61-90", "90+"]


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

def money_sum(field, **kwargs):
    return Coalesce(Sum(field, **kwargs), Value(ZERO), output_field=MONEY)


def total(queryset, field="amount"):
    return queryset.aggregate(t=money_sum(field))["t"]


def month_bounds(year, month):
    """Aware [start, end) datetimes covering one calendar month."""
    start = timezone.make_aware(datetime(year, month, 1))
    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    return start, timezone.make_aware(datetime(ny, nm, 1))


def day_bounds(date_from=None, date_to=None):
    """Aware [start, end) datetimes for an inclusive date range; either side may be None."""
    start = timezone.make_aware(datetime.combine(date_from, time.min)) if date_from else None
    end = (timezone.make_aware(datetime.combine(date_to + timedelta(days=1), time.min))
           if date_to else None)
    return start, end


def month_range(today, n):
    """The last n (year, month) pairs ending with today's month, oldest first."""
    year, month, out = today.year, today.month, []
    for _ in range(n):
        out.append((year, month))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return out[::-1]


def charges_with_paid(user):
    """RentCharges annotated with `paid` and `outstanding`, computed in SQL."""
    return (
        RentCharge.objects.filter(user=user)
        .annotate(paid=money_sum("payments__amount"))
        .annotate(outstanding=F("amount_due") - F("paid"))
    )


# ----------------------------------------------------------------------------
# charged vs collected, by charge month
# ----------------------------------------------------------------------------

def revenue_series(user, months, today=None):
    today = today or timezone.localdate()
    pairs = month_range(today, months)
    fy, fm = pairs[0]
    in_window = Q(year__gt=fy) | Q(year=fy, month__gte=fm)
    pay_window = Q(rent_charge__year__gt=fy) | Q(rent_charge__year=fy, rent_charge__month__gte=fm)

    charged = {
        (r["year"], r["month"]): r["total"]
        for r in (RentCharge.objects.filter(user=user).filter(in_window)
                  .order_by().values("year", "month").annotate(total=money_sum("amount_due")))
    }
    collected = {
        (r["rent_charge__year"], r["rent_charge__month"]): r["total"]
        for r in (Payment.objects.filter(user=user).filter(pay_window)
                  .order_by().values("rent_charge__year", "rent_charge__month")
                  .annotate(total=money_sum("amount")))
    }

    peak = max([ZERO] + [charged.get(p, ZERO) for p in pairs] + [collected.get(p, ZERO) for p in pairs])

    def pct(value):
        return round(float(value / peak * 100), 1) if peak else 0

    series = []
    for y, m in pairs:
        ch, co = charged.get((y, m), ZERO), collected.get((y, m), ZERO)
        series.append({
            "label": date(y, m, 1).strftime("%b %Y"),
            "charged": ch, "collected": co,
            "charged_percent": pct(ch), "collected_percent": pct(co),
        })
    return series


# ----------------------------------------------------------------------------
# arrears aging
# ----------------------------------------------------------------------------

def _bucket_label(days_overdue):
    if days_overdue <= 30:
        return "0-30"
    if days_overdue <= 60:
        return "31-60"
    if days_overdue <= 90:
        return "61-90"
    return "90+"


def arrears_aging(user, today=None):
    """
    Unpaid rent whose due date has passed, bucketed by days overdue.
    Charges that aren't due yet are not arrears and are excluded.
    """
    today = today or timezone.localdate()
    charges = (
        charges_with_paid(user)
        .filter(amount_due__gt=F("paid"))
        .select_related("tenant__house__flat_building")
        .order_by("year", "month")
    )

    totals = {label: ZERO for label in BUCKET_LABELS}
    tenants_in = {label: set() for label in BUCKET_LABELS}
    per_tenant = {}

    for charge in charges:
        tenant = charge.tenant
        days = (today - tenant.due_date_for(charge.year, charge.month)).days
        if days < 1:
            continue
        label = _bucket_label(days)
        totals[label] += charge.outstanding
        tenants_in[label].add(tenant.pk)
        row = per_tenant.setdefault(tenant.pk, {
            "tenant": tenant, "house": tenant.house, "amount": ZERO,
            "charges": 0, "oldest_days": 0,
        })
        row["amount"] += charge.outstanding
        row["charges"] += 1
        row["oldest_days"] = max(row["oldest_days"], days)

    rows = sorted(per_tenant.values(), key=lambda r: r["amount"], reverse=True)
    for row in rows:
        row["bucket"] = f"{_bucket_label(row['oldest_days'])} days"
        row["months_overdue"] = row["charges"]

    # empty list => the templates show their "no arrears" empty state
    buckets = [] if not rows else [
        {"label": label, "amount": totals[label], "tenant_count": len(tenants_in[label])}
        for label in BUCKET_LABELS
    ]
    return {
        "rows": rows,
        "buckets": buckets,
        "grand_total": sum(totals.values(), ZERO),
        "tenants_in_arrears": len(rows),
    }


# ----------------------------------------------------------------------------
# overview page
# ----------------------------------------------------------------------------

def overview(user, months=6, today=None):
    today = today or timezone.localdate()

    houses = House.objects.filter(user=user).aggregate(
        total=Count("id"), occupied=Count("id", filter=Q(occupation=True)))
    total_houses, occupied = houses["total"], houses["occupied"]

    series = revenue_series(user, months, today)
    charged_window = sum((p["charged"] for p in series), ZERO)
    collected_window = sum((p["collected"] for p in series), ZERO)

    start, end = month_bounds(today.year, today.month)
    received_this_month = total(Payment.objects.filter(user=user, paid_at__gte=start, paid_at__lt=end))

    current = series[-1]                 # the last point is always the current month
    ring_pct = (min(float(current["collected"] / current["charged"] * 100), 100)
                if current["charged"] else 0)

    arrears = arrears_aging(user, today)

    return {
        "range": months,
        "kpis": {
            "occupancy_rate": round(occupied / total_houses * 100, 1) if total_houses else 0,
            "collection_rate": (min(round(float(collected_window / charged_window * 100), 1), 100)
                                if charged_window else 0),
            "total_arrears": arrears["grand_total"],
            "monthly_revenue": received_this_month,
            "active_tenants": Tenant.objects.filter(user=user, is_active=True).count(),
            "vacant_houses": total_houses - occupied,
        },
        "revenue_series": series,
        "top_arrears": [
            {"tenant": r["tenant"], "months_overdue": r["months_overdue"], "amount": r["amount"]}
            for r in arrears["rows"][:5]
        ],
        "ring": {
            "percentage": round(ring_pct, 1),
            "dasharray": round(ring_pct / 100 * RING_CIRCUMFERENCE, 1),
            "collected": current["collected"],
            "charged": current["charged"],
        },
        "aging_buckets": arrears["buckets"],
    }


# ----------------------------------------------------------------------------
# occupancy page
# ----------------------------------------------------------------------------
def occupancy(user):
    houses = House.objects.order_by("house_number").prefetch_related(
        Prefetch("tenants", queryset=Tenant.objects.filter(is_active=True), to_attr="active_list"))
    buildings = (FlatBuilding.objects.filter(user=user).order_by("building_name")
                 .prefetch_related(Prefetch("houses", queryset=houses)))      # 3 queries total

    rows = []
    for building in buildings:
        tiles = []
        for house in building.houses.all():
            tenant = house.active_list[0] if house.active_list else None
            tiles.append({
                "number": house.house_number,
                "occupied": house.occupation,
                "tenant": tenant.full_name if tenant else None,
                "rent": house.house_rent_amount,
            })
        count = len(tiles)
        occupied = sum(1 for t in tiles if t["occupied"])
        rows.append({
            "building": building.building_name,
            "total": count, "occupied": occupied, "vacant": count - occupied,
            "rate": round(occupied / count * 100, 1) if count else 0,
            "houses": tiles,
        })
    return {"buildings": rows}


# ----------------------------------------------------------------------------
# rent charge history
# ----------------------------------------------------------------------------

def available_years(user, today=None):
    today = today or timezone.localdate()
    years = set(RentCharge.objects.filter(user=user).values_list("year", flat=True).distinct())
    years.add(today.year)
    return sorted(years, reverse=True)


def month_summaries(user, year):
    names = dict(RentCharge.MONTH_CHOICES)
    charged = {r["month"]: r["total"] for r in (
        RentCharge.objects.filter(user=user, year=year)
        .order_by().values("month").annotate(total=money_sum("amount_due")))}
    collected = {r["rent_charge__month"]: r["total"] for r in (
        Payment.objects.filter(user=user, rent_charge__year=year)
        .order_by().values("rent_charge__month").annotate(total=money_sum("amount")))}

    out = []
    for month in range(1, 13):
        ch = charged.get(month, ZERO)
        if not ch:
            continue
        co = collected.get(month, ZERO)
        out.append({
            "month": names[month], "charged": ch, "collected": co,
            "outstanding": max(ch - co, ZERO),
            "collection_rate": min(round(float(co / ch * 100), 1), 100),
        })
    return out


# ----------------------------------------------------------------------------
# tenant ledger: charges and payments merged by date with a running balance
# ----------------------------------------------------------------------------

def tenant_ledger(tenant):
    rows = []
    for c in tenant.rent_charges.all():
        rows.append({
            "date": tenant.due_date_for(c.year, c.month), "order": 0, "kind": "charge",
            "description": f"Rent {c.get_month_display()} {c.year}",
            "debit": c.amount_due, "credit": ZERO,
        })
    for p in tenant.payments.select_related("rent_charge"):
        ref = f" · {p.payment_reference}" if p.payment_reference else ""
        rows.append({
            "date": timezone.localtime(p.paid_at).date(), "order": 1, "kind": "payment",
            "description": (f"{p.get_payment_method_display()} for "
                            f"{p.rent_charge.get_month_display()} {p.rent_charge.year}{ref}"),
            "debit": ZERO, "credit": p.amount,
        })

    rows.sort(key=lambda r: (r["date"], r["order"]))      # same day: charge before payment
    running = ZERO
    for r in rows:
        running += r["debit"] - r["credit"]
        r["running_balance"] = running                    # positive = tenant owes
    return {
        "ledger_rows": rows,
        "balance": running,
        "credit_balance": max(ZERO, -running),
        "total_charged": sum((r["debit"] for r in rows), ZERO),
        "total_paid": sum((r["credit"] for r in rows), ZERO),
    }