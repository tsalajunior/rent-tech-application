from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db.models import DateField, Q, QuerySet, Sum
from django.db.models.functions import Coalesce

from .models import Location, LocationEquipement


ZERO = Decimal("0.00")


def _total(queryset, field):
    return queryset.aggregate(amount=Sum(field))["amount"] or ZERO


def _apply_date_range(queryset, field, start, end):
    if start is not None:
        queryset = queryset.filter(**{f"{field}__gte": start})
    if end is not None:
        queryset = queryset.filter(**{f"{field}__lte": end})
    return queryset


def _revenue_rows(queryset, fields, label_builder):
    rows = (
        queryset.values(*fields)
        .annotate(loyers=Sum("montant_total"), penalites=Sum("penalite_retard"))
        .order_by(*fields)
    )
    results = [
        {
            "label": label_builder(row),
            "amount": (row["loyers"] or ZERO) + (row["penalites"] or ZERO),
        }
        for row in rows
    ]
    return sorted(results, key=lambda item: (-item["amount"], item["label"]))


def build_financial_statistics(
    locations: QuerySet[Location],
    *,
    today: date,
    start: date | None,
    end: date | None,
) -> dict:
    completed = (
        locations.filter(Q(retour_reelle__isnull=False) | Q(statut="terminee"))
        .exclude(statut="annulee")
        .annotate(
            _date_finance=Coalesce(
                "retour_reelle", "retour_prevue", output_field=DateField()
            )
        )
    )
    completed = _apply_date_range(completed, "_date_finance", start, end)

    active = locations.filter(retour_reelle__isnull=True).exclude(
        statut__in=("terminee", "annulee")
    )
    active = _apply_date_range(active, "retour_prevue", start, end)

    total_loyers = _total(completed, "montant_total")
    penalites_generees = _total(completed, "penalite_retard")
    completed_rows = completed.select_related("client", "agence").order_by(
        "retour_reelle", "pk"
    )

    cautions_a_restituer = ZERO
    cautions_a_restituer_sans_retard = ZERO
    cautions_retenues = ZERO
    for location in completed_rows:
        penalite = location.penalite_retard or ZERO
        cautions_a_restituer += location.montant_caution_a_rembourser
        cautions_retenues += min(location.caution, penalite)
        if (
            location.retour_reelle is not None
            and location.retour_reelle <= location.retour_prevue
            and penalite == ZERO
        ):
            cautions_a_restituer_sans_retard += location.caution

    locations_en_attente = []
    loyers_en_attente = ZERO
    penalites_en_attente = ZERO
    active_rows = active.select_related("client", "agence").order_by(
        "retour_prevue", "pk"
    )
    for location in active_rows:
        penalite = (location.penalite_retard or ZERO) + (
            location.calculer_penalite_retard(today)
        )
        montant_attendu = location.montant_total + penalite
        loyers_en_attente += location.montant_total
        penalites_en_attente += penalite
        locations_en_attente.append(
            {
                "id": location.pk,
                "agence": location.agence.nom,
                "client": " ".join(
                    part
                    for part in (
                        location.client.prenom,
                        location.client.nom,
                    )
                    if part
                ),
                "echeance": location.retour_prevue,
                "loyer": location.montant_total,
                "penalite": penalite,
                "montant_attendu": montant_attendu,
                "caution": location.caution,
            }
        )

    equipment_totals = defaultdict(lambda: ZERO)
    equipment_lines = (
        LocationEquipement.objects.filter(
            location_id__in=completed.order_by().values("pk")
        )
        .select_related("location", "equipement")
        .order_by("equipement__nom", "equipement__reference")
    )
    for line in equipment_lines:
        jours_prevus = max(
            0, (line.location.retour_prevue - line.location.date_debut).days
        )
        equipment_totals[
            (line.equipement_id, line.equipement.nom, line.equipement.reference)
        ] += line.prix_journalier_applique * jours_prevus

    revenus_par_equipement = [
        {
            "label": f"{nom} ({reference})",
            "amount": amount,
        }
        for (_, nom, reference), amount in equipment_totals.items()
    ]
    revenus_par_equipement.sort(
        key=lambda item: (-item["amount"], item["label"])
    )

    return {
        "nombre_locations_terminees": completed.count(),
        "chiffre_affaires": total_loyers + penalites_generees,
        "loyers_generes": total_loyers,
        "penalites_generees": penalites_generees,
        "loyers_en_attente": loyers_en_attente,
        "penalites_en_attente": penalites_en_attente,
        "montant_en_attente": loyers_en_attente + penalites_en_attente,
        "cautions_a_restituer": cautions_a_restituer,
        "cautions_a_restituer_sans_retard": cautions_a_restituer_sans_retard,
        "cautions_retenues": cautions_retenues,
        "revenus_par_agence": _revenue_rows(
            completed,
            ("agence_id", "agence__nom"),
            lambda row: row["agence__nom"],
        ),
        "revenus_par_client": _revenue_rows(
            completed,
            ("client_id", "client__prenom", "client__nom"),
            lambda row: " ".join(
                part
                for part in (row["client__prenom"], row["client__nom"])
                if part
            ),
        ),
        "revenus_par_equipement": revenus_par_equipement,
        "locations_en_attente": locations_en_attente,
    }
