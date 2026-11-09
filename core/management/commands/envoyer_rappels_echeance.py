from datetime import timedelta
import time

from django.core.management.base import BaseCommand
from django.urls import reverse
from django.utils import timezone

from core.models import Location
from core.notifications import notify_event


class Command(BaseCommand):
    help = "Crée les notifications quotidiennes de rappel des échéances de location."

    def add_arguments(self, parser):
        parser.add_argument(
            "--loop",
            action="store_true",
            help="Répète le traitement chaque jour à 08:00, heure locale.",
        )

    def handle(self, *args, **options):
        self._envoyer_rappels()
        if not options.get("loop"):
            return

        while True:
            maintenant = timezone.localtime()
            prochain_traitement = maintenant.replace(
                hour=8, minute=0, second=0, microsecond=0
            )
            if prochain_traitement <= maintenant:
                prochain_traitement += timedelta(days=1)
            time.sleep((prochain_traitement - maintenant).total_seconds())
            self._envoyer_rappels()

    def _envoyer_rappels(self):
        aujourd_hui = timezone.localdate()
        demain = aujourd_hui + timedelta(days=1)
        locations = (
            Location.objects.filter(
                retour_reelle__isnull=True,
                statut__in=("en_cours", "etendue", "retard"),
            )
            .select_related("client", "agence")
            .order_by("pk")
        )
        notifications_creees = 0

        for location in locations:
            if location.retour_prevue == demain:
                event_type = "rental_due_tomorrow"
                title = "Échéance de location dans 24 heures"
                message = (
                    f"La location #{location.pk} de {location.client} arrive "
                    f"à échéance le {location.retour_prevue:%d/%m/%Y}."
                )
            elif location.retour_prevue == aujourd_hui:
                event_type = "rental_due_today"
                title = "Échéance de location aujourd’hui"
                message = (
                    f"La location #{location.pk} de {location.client} doit être "
                    f"retournée aujourd’hui ({location.retour_prevue:%d/%m/%Y})."
                )
            elif location.retour_prevue < aujourd_hui:
                event_type = "rental_overdue"
                title = "Location en retard"
                message = (
                    f"La location #{location.pk} de {location.client} est en retard "
                    f"depuis le {location.retour_prevue:%d/%m/%Y}. "
                    "Une pénalité journalière continue de s’appliquer jusqu’au retour."
                )
            else:
                continue

            notify_event(
                actor=None,
                agency=location.agence,
                event_type=event_type,
                title=title,
                message=message,
                target_url=reverse("core:detail_location", args=[location.pk]),
                event_key=(
                    f"reminder:{event_type}:{location.pk}:{aujourd_hui.isoformat()}"
                ),
            )
            notifications_creees += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Traitement terminé : {notifications_creees} location(s) "
                "d’échéance traitée(s)."
            )
        )
