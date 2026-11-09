from uuid import uuid4

from django.contrib.auth.models import User
from django.urls import reverse

from .models import Notification, ProfilEmploye


def _recipients_for_event(actor, agency):
    recipients = set(
        User.objects.filter(
            is_active=True,
            is_superuser=True,
        ).values_list("pk", flat=True)
    )
    if agency is not None and (actor is None or actor.is_superuser):
        recipients.update(
            ProfilEmploye.objects.filter(
                agence=agency, user__is_active=True
            ).values_list("user_id", flat=True)
        )
    if actor is not None and actor.is_superuser:
        recipients.discard(actor.pk)
    return recipients


def notify_event(
    *,
    actor,
    agency,
    event_type,
    title,
    message,
    target_url="",
    event_key=None,
):
    event_key = event_key or f"{event_type}:{uuid4().hex}"
    actor_name = (
        actor.get_full_name().strip() or actor.username if actor is not None else "Système"
    )
    full_message = f"{message} Action effectuée par : {actor_name}."
    Notification.objects.bulk_create(
        [
            Notification(
                recipient_id=recipient_id,
                actor=actor,
                agence=agency,
                event_type=event_type,
                title=title,
                message=full_message,
                target_url=target_url,
                event_key=f"{event_key}:{recipient_id}",
            )
            for recipient_id in _recipients_for_event(actor, agency)
        ],
        ignore_conflicts=True,
    )


def notify_location_event(
    location, actor, event_type, title, message, target_url=None
):
    notify_event(
        actor=actor,
        agency=location.agence,
        event_type=event_type,
        title=title,
        message=message,
        target_url=target_url or reverse("core:detail_location", args=[location.pk]),
    )


def notify_equipment_event(equipment, actor, title, message, event_type):
    notify_event(
        actor=actor,
        agency=equipment.agence,
        event_type=event_type,
        title=title,
        message=message,
        target_url=reverse("core:liste_equipements"),
    )
