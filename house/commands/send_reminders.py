from django.core.management.base import BaseCommand

from tennants.services.tasks import send_daily_rent_reminders, send_overdue_notices


class Command(BaseCommand):
    help = "Send rent reminders (and optionally overdue notices) via SMS"

    def add_arguments(self, parser):
        parser.add_argument("--overdue", action="store_true", help="Also send overdue notices")

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(send_daily_rent_reminders()))
        if options["overdue"]:
            self.stdout.write(self.style.SUCCESS(send_overdue_notices()))