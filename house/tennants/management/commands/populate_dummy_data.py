import calendar
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from tennants.models import FlatBuilding, House, Payment, RentCharge, Tenant


class Command(BaseCommand):
    help = "Create isolated demo landlords and realistic rental data (DEBUG only)."

    def add_arguments(self, parser):
        parser.add_argument("--users", type=int, default=10)
        parser.add_argument("--tenants-per-user", type=int, default=10)
        parser.add_argument("--months", type=int, default=12)
        parser.add_argument("--password", default="DemoPass123!")

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo data can only be generated when DEBUG=True.")

        user_count = options["users"]
        tenant_count = options["tenants_per_user"]
        month_count = options["months"]
        if user_count < 10:
            raise CommandError("--users must be at least 10.")
        if tenant_count < 1 or month_count < 1 or tenant_count * month_count < 100:
            raise CommandError(
                "--tenants-per-user multiplied by --months must create at least 100 rent charges per user."
            )
        if not options["password"]:
            raise CommandError("--password cannot be empty.")

        totals = {"users": 0, "buildings": 0, "houses": 0, "tenants": 0, "charges": 0, "payments": 0}
        today = timezone.localdate()
        due_date = today.replace(day=5)

        for user_number in range(1, user_count + 1):
            username = f"demo_landlord_{user_number:02d}"
            email = f"{username}@example.test"
            with transaction.atomic():
                user, created = User.objects.get_or_create(
                    username=username,
                    defaults={"email": email, "first_name": "Demo", "last_name": f"Landlord {user_number}"},
                )
                if created:
                    user.set_password(options["password"])
                    user.save(update_fields=["password"])
                elif user.email != email or user.is_staff or user.is_superuser:
                    raise CommandError(
                        f"Refusing to use existing account {username}; expected a regular demo account "
                        f"with email {email}."
                    )
                else:
                    user.set_password(options["password"])
                    user.save(update_fields=["password"])
                totals["users"] += int(created)

                building, created = FlatBuilding.objects.get_or_create(
                    user=user,
                    building_name="Demo Apartments",
                    defaults={"address": f"{user_number} Sample Road", "number_of_houses": tenant_count},
                )
                totals["buildings"] += int(created)
                if building.number_of_houses < tenant_count:
                    building.number_of_houses = tenant_count
                    building.save(update_fields=["number_of_houses"])

                for tenant_number in range(1, tenant_count + 1):
                    house_number = f"H{tenant_number:04d}"
                    rent = Decimal("15000.00") + Decimal(tenant_number % 5) * Decimal("1000.00")
                    house, created = House.objects.get_or_create(
                        flat_building=building,
                        house_number=house_number,
                        defaults={
                            "user": user,
                            "house_size": "2 bedroom",
                            "house_rent_amount": rent,
                            "deposit_amount": rent,
                        },
                    )
                    totals["houses"] += int(created)
                    if house.user_id != user.pk:
                        raise CommandError(f"Existing demo house {house_number} has unexpected ownership.")
                    rent = house.house_rent_amount

                    global_tenant_number = (user_number - 1) * tenant_count + tenant_number
                    tenant_email = f"demo-tenant-{global_tenant_number:06d}@example.test"
                    tenant, created = Tenant.objects.get_or_create(
                        email=tenant_email,
                        defaults={
                            "user": user,
                            "full_name": f"Demo Tenant {user_number:02d}-{tenant_number:03d}",
                            "phone": f"+2547{global_tenant_number:08d}",
                            "id_number": f"{global_tenant_number:010d}",
                            "house": house,
                            "rent_due_date": due_date,
                            "sms_notifications": False,
                        },
                    )
                    if tenant.user_id != user.pk or tenant.house_id != house.pk:
                        raise CommandError(f"Existing demo tenant {tenant_email} has unexpected ownership or house.")
                    totals["tenants"] += int(created)
                    if tenant.sms_notifications:
                        tenant.sms_notifications = False
                        tenant.save(update_fields=["sms_notifications"])

                    for month_offset in reversed(range(month_count)):
                        month_index = today.year * 12 + today.month - 1 - month_offset
                        year, zero_based_month = divmod(month_index, 12)
                        month = zero_based_month + 1
                        charge, created = RentCharge.objects.get_or_create(
                            tenant=tenant,
                            year=year,
                            month=month,
                            defaults={"user": user, "amount_due": rent},
                        )
                        totals["charges"] += int(created)

                        if month_offset == 0:
                            payment_state = tenant_number % 3
                        else:
                            payment_state = (tenant_number + month_offset) % 5
                        if payment_state == 0:
                            continue

                        amount = rent if payment_state in (2, 3, 4) else rent / 2
                        reference = f"DEMO-{user.pk}-{tenant.pk}-{year}{month:02d}"
                        if Payment.objects.filter(
                            user=user, rent_charge=charge, payment_reference=reference
                        ).exists():
                            continue

                        day = min(5, calendar.monthrange(year, month)[1])
                        paid_at = timezone.make_aware(datetime(year, month, day, 12))
                        payment = Payment(
                            user=user,
                            tenant=tenant,
                            rent_charge=charge,
                            amount=amount,
                            payment_method="mobile_money",
                            payment_reference=reference,
                            paid_at=paid_at,
                        )
                        payment._skip_sms = True
                        payment.save()
                        totals["payments"] += 1

        self.stdout.write(self.style.SUCCESS("Demo data is ready."))
        self.stdout.write(
            "Created: "
            + ", ".join(f"{count} {name}" for name, count in totals.items())
        )
        self.stdout.write("Demo logins: demo_landlord_01 through demo_landlord_10 (and any additional accounts).")
        self.stdout.write(f"Shared demo password: {options['password']}")
