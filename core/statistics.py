import calendar
from collections.abc import Iterable
from datetime import date, datetime

from django.db.models import Count, F, Q, QuerySet
from django.db.models.functions import TruncMonth

from .models import Location, LocationEquipement


STATUS_CHOICES = (
    ("en_cours", "En cours"),
    ("etendue", "Étendue"),
    ("retard", "En retard"),
    ("terminee", "Terminée"),
    ("annulee", "Annulée"),
)


def filter_location_status(
    locations: QuerySet[Location], status: str, today: date
) -> QuerySet[Location]:
    if status == "annulee":
        return locations.filter(statut="annulee")
    if status == "terminee":
        return locations.filter(Q(retour_reelle__isnull=False) | Q(statut="terminee"))

    active = locations.filter(
        retour_reelle__isnull=True
    ).exclude(statut__in=("terminee", "annulee"))
    if status == "retard":
        return active.filter(retour_prevue__lt=today)
    if status == "etendue":
        return active.filter(statut="etendue", retour_prevue__gte=today)
    if status == "en_cours":
        return active.exclude(statut="etendue").filter(retour_prevue__gte=today)
    return locations


def _month_starts(start: date, end: date) -> list[date]:
    months = []
    current = start.replace(day=1)
    last = end.replace(day=1)
    while current <= last:
        months.append(current)
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    return months


def _month_date(value: date | datetime) -> date:
    return value.date() if isinstance(value, datetime) else value


def _month_labels(
    counts: dict[date, int], start: date | None, end: date | None, today: date
) -> tuple[list[str], list[int]]:
    if start is None:
        start = min(counts) if counts else date(today.year, today.month, 1)
    if end is None:
        end = max(counts) if counts else date(today.year, today.month, 1)

    months = _month_starts(start, end)
    return (
        [month.strftime("%m/%Y") for month in months],
        [counts.get(month, 0) for month in months],
    )


def _top_counts(queryset: Iterable[dict], label_key: str) -> tuple[list[str], list[int]]:
    rows = list(queryset)
    return (
        [str(row[label_key]) for row in rows],
        [row["total"] for row in rows],
    )


def _chart_items(labels: list[str], values: list[int]) -> list[dict]:
    maximum = max(values, default=0)
    return [
        {
            "label": label,
            "value": value,
            "width": round(value / maximum * 100) if maximum else 0,
            "height": round(value / maximum * 100) if maximum else 0,
        }
        for label, value in zip(labels, values)
    ]


def build_location_statistics(
    locations: QuerySet[Location],
    *,
    today: date,
    start: date | None,
    end: date | None,
    agency_comparison: bool,
    agency_filter_applied: bool,
    status: str,
    accessible_agency_ids: QuerySet,
) -> dict:
    monthly_rows = (
        locations.annotate(month=TruncMonth("date_debut"))
        .values("month")
        .annotate(total=Count("pk"))
        .order_by("month")
    )
    monthly_counts = {
        _month_date(row["month"]).replace(day=1): row["total"]
        for row in monthly_rows
        if row["month"] is not None
    }
    monthly_labels, monthly_values = _month_labels(
        monthly_counts, start, end, today
    )

    location_ids = locations.order_by().values("pk")
    equipment_rows = (
        LocationEquipement.objects.filter(location_id__in=location_ids)
        .values("equipement__nom", "equipement__categorie__nom")
        .annotate(total=Count("location_id", distinct=True))
        .order_by("-total", "equipement__nom")[:10]
    )
    equipment_labels, equipment_values = _top_counts(
        (
            {
                "label": (
                    f"{row['equipement__nom']} "
                    f"({row['equipement__categorie__nom']})"
                ),
                "total": row["total"],
            }
            for row in equipment_rows
        ),
        "label",
    )

    category_rows = (
        LocationEquipement.objects.filter(location_id__in=location_ids)
        .values("equipement__categorie__nom")
        .annotate(total=Count("location_id", distinct=True))
        .order_by("-total", "equipement__categorie__nom")[:10]
    )
    category_labels, category_values = _top_counts(
        (
            {"label": row["equipement__categorie__nom"], "total": row["total"]}
            for row in category_rows
        ),
        "label",
    )

    client_rows = (
        locations.values("client__nom", "client__prenom")
        .annotate(total=Count("pk"))
        .order_by("-total", "client__nom", "client__prenom")[:10]
    )
    client_labels, client_values = _top_counts(
        (
            {
                "label": " ".join(
                    part
                    for part in (row["client__prenom"], row["client__nom"])
                    if part
                ),
                "total": row["total"],
            }
            for row in client_rows
        ),
        "label",
    )

    if agency_comparison and not agency_filter_applied:
        agency_rows = (
            locations.values("agence__nom")
            .annotate(total=Count("pk"))
            .order_by("-total", "agence__nom")
        )
        agency_labels, agency_values = _top_counts(
            (
                {"label": row["agence__nom"], "total": row["total"]}
                for row in agency_rows
            ),
            "label",
        )
    else:
        agency_labels, agency_values = [], []

    current_overdue = locations.filter(
        retour_reelle__isnull=True,
        retour_prevue__lt=today,
    ).exclude(statut__in=("terminee", "annulee")).count()
    if status not in ("tout", "retard"):
        current_overdue = 0

    if status in ("tout", "terminee"):
        late_returns = Location.objects.filter(
            agence_id__in=accessible_agency_ids,
            retour_reelle__isnull=False,
            retour_reelle__gt=F("retour_prevue"),
        )
        if start is not None:
            late_returns = late_returns.filter(retour_reelle__gte=start)
        if end is not None:
            late_returns = late_returns.filter(retour_reelle__lte=end)
        late_rows = (
            late_returns.annotate(month=TruncMonth("retour_reelle"))
            .values("month")
            .annotate(total=Count("pk"))
            .order_by("month")
        )
    else:
        late_rows = []
    late_counts = {
        _month_date(row["month"]).replace(day=1): row["total"]
        for row in late_rows
        if row["month"] is not None
    }
    late_labels, late_values = _month_labels(late_counts, start, end, today)

    chart_data = {
        "monthly": _chart_items(monthly_labels, monthly_values),
        "equipment": _chart_items(equipment_labels, equipment_values),
        "categories": _chart_items(category_labels, category_values),
        "agencies": _chart_items(agency_labels, agency_values),
        "clients": _chart_items(client_labels, client_values),
        "late_returns": _chart_items(late_labels, late_values),
    }

    return {
        "total_locations": locations.count(),
        "current_overdue": current_overdue,
        "monthly_labels": monthly_labels,
        "monthly_values": monthly_values,
        "equipment_labels": equipment_labels,
        "equipment_values": equipment_values,
        "category_labels": category_labels,
        "category_values": category_values,
        "agency_labels": agency_labels,
        "agency_values": agency_values,
        "client_labels": client_labels,
        "client_values": client_values,
        "late_labels": late_labels,
        "late_values": late_values,
        "charts": chart_data,
    }
