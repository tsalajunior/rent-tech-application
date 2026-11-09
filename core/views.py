import csv
from io import BytesIO, StringIO

from django.contrib.staticfiles import finders
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponse

from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from .models import (
    Agence,
    Categorie,
    Equipement,
    Client,
    Location,
    LocationEquipement,
    ProlongationLocation,
    Notification,
    ProfilEmploye,
)
from .notifications import (
    notify_equipment_event,
    notify_location_event,
    notify_event,
)
from django.views.decorators.cache import never_cache
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from xml.sax.saxutils import escape
from .forms import (
    ClientForm,
    EquipementForm,
    AdminUserForm,
    UserProfileForm,
    CategorieForm,
    AgenceForm,
    LocationForm,
    ProlongationLocationForm,
)

RENTTECH_NAME = "RentTech"
RENTTECH_DESCRIPTION = (
    "Système de location de matériels informatiques et électroniques."
)


def _location_accessible(user, location):
    if user.is_superuser:
        return True
    try:
        return location.agence_id == user.profil.agence_id
    except AttributeError:
        return False


def _location_est_cloturee(location):
    return bool(
        location.retour_reelle
        or location.statut in ("terminee", "annulee")
    )


def _prix_location(equipements, duree):
    montant = sum(
        (equipement.prix_journalier for equipement in equipements),
        Decimal("0.00"),
    ) * duree
    return montant.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _arrondir_montant(montant):
    return montant.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _csv_response(filename, headers, rows):
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(
            [
                "'" + value
                if isinstance(value, str)
                and value.lstrip(" \t\r\n")[:1] in ("=", "+", "-", "@")
                else value
                for value in row
            ]
        )

    response = HttpResponse(
        "\ufeff" + output.getvalue(), content_type="text/csv; charset=utf-8"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _agence_queryset_for_user(user, queryset):
    if user.is_superuser:
        return queryset
    try:
        agence_id = user.profil.agence_id
    except AttributeError:
        return queryset.none()
    return queryset.filter(agence_id=agence_id) if agence_id else queryset.none()


def _montants_location_csv(location, aujourd_hui):
    penalite = location.penalite_retard
    if location.est_active:
        penalite += location.calculer_penalite_retard(aujourd_hui)
    penalite = _arrondir_montant(penalite)

    if location.statut == "annulee":
        remboursement = (
            location.montant_loyer_a_rembourser + location.caution
        )
        montant_final = location.montant_loyer_conserve
    else:
        remboursement = max(location.caution - penalite, Decimal("0.00"))
        montant_final = location.montant_total + penalite

    return _arrondir_montant(remboursement), _arrondir_montant(montant_final)


@login_required
@never_cache
def liste_notifications(request):
    notifications = Notification.objects.filter(
        recipient=request.user
    ).select_related("actor", "agence")
    page_obj = Paginator(notifications, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "core/pages/liste_notifications.html",
        {"page_obj": page_obj},
    )


@login_required
@never_cache
def ouvrir_notification(request, pk):
    if request.method != "POST":
        return redirect("core:liste_notifications")
    notification = get_object_or_404(
        Notification, pk=pk, recipient=request.user
    )
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])
    return redirect(notification.target_url or "core:liste_notifications")


@login_required
@never_cache
def marquer_notifications_lues(request):
    if request.method != "POST":
        return redirect("core:liste_notifications")
    Notification.objects.filter(
        recipient=request.user, read_at__isnull=True
    ).update(read_at=timezone.now())
    return redirect("core:liste_notifications")


# dashboard dynamique pour l'administrateur central et les employés
@login_required
@never_cache
def dashboard(request):
    """
    Tableau de bord dynamique :
    - Vue globale pour l'administrateur principal.
    - Vue filtrée par agence pour l'employé simple.
    """
    user = request.user

    # if user.is_superuser:
    #     # Vue globale SuperAdmin
    #     total_clients = Client.objects.count()
    #     total_equipements = Equipement.objects.count()
    #     locations_en_cours = Location.objects.filter(retour_reelle__isnull=True).count()
    #     agence_libelle = "Administration Centrale (Toutes les Agences)"
    # else:
    #     # Vue restreinte à l'agence de l'employé
    #     try:
    #         employe_agence = user.profil.agence
    #     except AttributeError:
    #         employe_agence = None

    #     if employe_agence:
    #         # Filtrage strict par agence
    #         total_equipements = Equipement.objects.filter(agence=employe_agence).count()
    #         locations_en_cours = Location.objects.filter(
    #             agence=employe_agence, retour_reelle__isnull=True
    #         ).count()
    #         # Clients ayant effectué une location dans cette agence
    #         total_clients = (
    #             Client.objects.filter(locations__agence=employe_agence)
    #             .distinct()
    #             .count()
    #         )
    #         agence_libelle = f"Agence de {employe_agence.ville} ({employe_agence.nom})"
    #     else:
    #         total_equipements = 0
    #         locations_en_cours = 0
    #         total_clients = 0
    #         agence_libelle = "Aucune agence assignée"

    # context = {
    #     "total_clients": total_clients,
    #     "total_equipements": total_equipements,
    #     "locations_en_cours": locations_en_cours,
    #     "agence_libelle": agence_libelle,
    # }
    # return render(request, "core/pages/dashboard.html", context)
    if user.is_superuser:
        # Vue globale à 360° pour l'administrateur central
        total_equipements = Equipement.objects.count()
        total_clients = Client.objects.count()
        locations_en_cours = Location.objects.filter(
            retour_reelle__isnull=True,
            statut__in=("en_cours", "etendue", "retard"),
        ).count()
        agence_libelle = "Administration Centrale (Vue globale)"
    else:
        try:
            employe_agence = user.profil.agence
            # Filtrage strict par agence pour l'employé
            total_equipements = Equipement.objects.filter(agence=employe_agence).count()
            total_clients = Client.objects.filter(agence=employe_agence).count()
            locations_en_cours = Location.objects.filter(
                agence=employe_agence,
                retour_reelle__isnull=True,
                statut__in=("en_cours", "etendue", "retard"),
            ).count()
            agence_libelle = f"Agence de {employe_agence.ville} ({employe_agence.nom})"
        except AttributeError:
            total_equipements = 0
            total_clients = 0
            locations_en_cours = 0
            agence_libelle = "Aucune agence rattachée"

    context = {
        "total_clients": total_clients,
        "total_equipements": total_equipements,
        "locations_en_cours": locations_en_cours,
        "agence_libelle": agence_libelle,
    }
    return render(request, "core/pages/dashboard.html", context)


# Equiepements : liste, ajout, modification, suppression
@login_required
@never_cache
def liste_equipements(request):
    user = request.user
    query = request.GET.get("q", "")
    sort_by = request.GET.get("sort", "-id")  # Tri par défaut (les plus récents)

    # 1. Filtrage initial selon le cloisonnement agence / superuser
    if user.is_superuser:
        equipements = Equipement.objects.all()
    else:
        try:
            employe_agence = user.profil.agence
            equipements = Equipement.objects.filter(agence=employe_agence)
        except AttributeError:
            equipements = Equipement.objects.none()

    # 2. Filtrage dynamique par la barre de recherche
    if query:
        equipements = equipements.filter(
            Q(reference__icontains=query)
            | Q(nom__icontains=query)
            | Q(categorie__nom__icontains=query)
        )

    # 3. Dictionnaire de sécurisation et d'association des tris
    allowed_sorts = {
        "reference": "reference",
        "-reference": "-reference",
        "nom": "nom",
        "-nom": "-nom",
        "categorie": "categorie__nom",
        "-categorie": "-categorie",
        "agence": "agence__nom",
        "-agence": "-agence",
        "statut": "statut",
        "-statut": "-statut",
    }

    # Appliquer le tri s'il est valide, sinon tri par défaut
    if sort_by in allowed_sorts:
        equipements = equipements.order_by(allowed_sorts[sort_by])
    else:
        equipements = equipements.order_by("-id")

    # 4. Pagination : 10 éléments par page
    paginator = Paginator(equipements, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "equipements": page_obj,
        "query": query,
        "current_sort": sort_by,  # Transmis au template pour gérer l'affichage des flèches
    }
    return render(request, "core/pages/liste_equipements.html", context)


@login_required
@never_cache
def exporter_equipements_csv(request):
    equipements = _agence_queryset_for_user(
        request.user,
        Equipement.objects.select_related("categorie", "agence").order_by("pk"),
    )
    rows = (
        (
            equipement.pk,
            equipement.reference,
            equipement.nom,
            equipement.prix_journalier,
            equipement.get_statut_display(),
            equipement.categorie.nom,
            equipement.agence.nom,
        )
        for equipement in equipements
    )
    return _csv_response(
        "equipements.csv",
        ("#ID", "Référence", "Nom", "Prix journalier", "Statut", "Catégorie", "Agence"),
        rows,
    )


@login_required
@never_cache
def equipement_ajouter(request):
    # Réservé exclusivement à l'administrateur central
    if not request.user.is_superuser:
        return redirect("core:liste_equipements")

    if request.method == "POST":
        form = EquipementForm(request.POST)
        if form.is_valid():
            if form.cleaned_data["statut"] == "loue":
                form.add_error(
                    "statut",
                    "Un équipement ne peut passer à l'état loué que lorsqu'il est associé à une location.",
                )
            else:
                equipement = form.save()
                notify_equipment_event(
                    equipment=equipement,
                    actor=request.user,
                    title="Nouvel équipement affecté à votre agence",
                    message=(
                        f"L’équipement {equipement.reference} — {equipement.nom} "
                        f"a été ajouté au stock avec le statut "
                        f"{equipement.get_statut_display()}."
                    ),
                    event_type="equipment_created",
                )
                return redirect("core:liste_equipements")
    else:
        form = EquipementForm()

    context = {
        "form": form,
        "action": "Ajouter",
    }
    return render(request, "core/pages/equipement_form.html", context)


@login_required
@never_cache
def equipement_supprimer(request, pk):
    # Sécurité supplémentaire : seuls les administrateurs peuvent supprimer
    if not request.user.is_superuser:
        return redirect("core:liste_equipements")

    if request.method == "POST":
        with transaction.atomic():
            equipement = get_object_or_404(
                Equipement.objects.select_for_update(), pk=pk
            )
            location_active = LocationEquipement.objects.filter(
                equipement=equipement,
                location__retour_reelle__isnull=True,
                location__statut__in=("en_cours", "etendue", "retard"),
            ).exists()
            if location_active:
                messages.error(
                    request,
                    "Cet équipement est associé à une location active et ne peut pas être supprimé.",
                )
                return redirect("core:liste_equipements")
            ancienne_agence = equipement.agence
            equipement.delete()
            notify_event(
                actor=request.user,
                agency=ancienne_agence,
                event_type="equipment_deleted",
                title="Équipement retiré du stock",
                message=(
                    f"L’équipement {equipement.reference} — {equipement.nom} "
                    f"a été supprimé du parc de l’agence."
                ),
                target_url=reverse("core:liste_equipements"),
            )
        return redirect("core:liste_equipements")

    equipement = get_object_or_404(Equipement, pk=pk)
    if LocationEquipement.objects.filter(
        equipement=equipement,
        location__retour_reelle__isnull=True,
        location__statut__in=("en_cours", "etendue", "retard"),
    ).exists():
        messages.error(
            request,
            "Cet équipement est associé à une location active et ne peut pas être supprimé.",
        )
        return redirect("core:liste_equipements")

    return render(
        request,
        "core/pages/equipement_confirmer_suppression.html",
        {"equipement": equipement},
    )


@login_required
@never_cache
def equipement_modifier(request, pk):
    # Réservé exclusivement aux administrateurs
    if not request.user.is_superuser:
        return redirect("core:liste_equipements")

    if request.method == "POST":
        with transaction.atomic():
            equipement = get_object_or_404(
                Equipement.objects.select_for_update(), pk=pk
            )
            location_active = LocationEquipement.objects.filter(
                equipement=equipement,
                location__retour_reelle__isnull=True,
                location__statut__in=("en_cours", "etendue", "retard"),
            ).exists()
            if location_active:
                messages.error(
                    request,
                    "Cet équipement est loué dans une location active et ne peut pas être modifié.",
                )
                return redirect("core:liste_equipements")

            ancienne_agence = equipement.agence
            ancien_statut = equipement.statut
            form = EquipementForm(request.POST, instance=equipement)
            if form.is_valid():
                if form.cleaned_data["statut"] == "loue":
                    form.add_error(
                        "statut",
                        "Un équipement ne peut être marqué loué que lorsqu'il est associé à une location active.",
                    )
                else:
                    equipement = form.save()
                    if (
                        ancienne_agence.pk != equipement.agence_id
                        or ancien_statut != equipement.statut
                    ):
                        changements = []
                        if ancienne_agence.pk != equipement.agence_id:
                            changements.append(
                                f"affecté à l’agence {equipement.agence.nom}"
                            )
                        if ancien_statut != equipement.statut:
                            changements.append(
                                f"statut : {equipement.get_statut_display()}"
                            )
                        notify_equipment_event(
                            equipment=equipement,
                            actor=request.user,
                            title="Mise à jour du parc de votre agence",
                            message=(
                                f"L’équipement {equipement.reference} — "
                                f"{equipement.nom} a été mis à jour "
                                f"({', '.join(changements)})."
                            ),
                            event_type="equipment_updated",
                        )
                        if ancienne_agence.pk != equipement.agence_id:
                            notify_event(
                                actor=request.user,
                                agency=ancienne_agence,
                                event_type="equipment_reassigned",
                                title="Équipement réaffecté à une autre agence",
                                message=(
                                    f"L’équipement {equipement.reference} — "
                                    f"{equipement.nom} a été transféré vers "
                                    f"l’agence {equipement.agence.nom}."
                                ),
                                target_url=reverse("core:liste_equipements"),
                            )
                    return redirect("core:liste_equipements")
    else:
        equipement = get_object_or_404(Equipement, pk=pk)
        location_active = LocationEquipement.objects.filter(
            equipement=equipement,
            location__retour_reelle__isnull=True,
            location__statut__in=("en_cours", "etendue", "retard"),
        ).exists()
        if location_active:
            messages.error(
                request,
                "Cet équipement est loué dans une location active et ne peut pas être modifié.",
            )
            return redirect("core:liste_equipements")
        form = EquipementForm(instance=equipement)

    context = {
        "form": form,
        "equipement": equipement,
    }
    return render(request, "core/pages/equipement_form.html", context)


# Clients : liste, ajout, modification, suppression
@login_required
@never_cache
def liste_clients(request):
    """
    Liste des clients filtrée par agence pour les employés.
    """
    user = request.user
    query = request.GET.get("q", "")
    sort_by = request.GET.get("sort", "-id")

    # Cloisonnement agence / superuser
    if user.is_superuser:
        clients = Client.objects.all()
    else:
        try:
            employe_agence = user.profil.agence
            clients = Client.objects.filter(agence=employe_agence)
        except AttributeError:
            clients = Client.objects.none()

    # Recherche dynamique (Nom, Prénom, Email ou Téléphone)
    if query:
        clients = clients.filter(
            Q(nom__icontains=query)
            | Q(prenom__icontains=query)
            | Q(email__icontains=query)
            | Q(telephone__icontains=query)
        )

    # Tris autorisés
    allowed_sorts = {
        "nom": "nom",
        "-nom": "-nom",
        "email": "email",
        "-email": "-email",
        "agence": "agence__nom",
        "-agence": "-agence",
    }

    if sort_by in allowed_sorts:
        clients = clients.order_by(allowed_sorts[sort_by])
    else:
        clients = clients.order_by("-id")

    # Pagination (10 éléments par page)
    paginator = Paginator(clients, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "clients": page_obj,
        "query": query,
        "current_sort": sort_by,
        "page_obj": page_obj,
    }
    return render(request, "core/pages/liste_clients.html", context)


@login_required
@never_cache
def exporter_clients_csv(request):
    clients = _agence_queryset_for_user(
        request.user, Client.objects.select_related("agence").order_by("pk")
    )
    rows = (
        (
            client.pk,
            client.nom,
            client.prenom or "",
            client.email,
            client.telephone,
            client.agence.nom,
        )
        for client in clients
    )
    return _csv_response(
        "clients.csv",
        ("#ID", "Nom", "Prénom", "Email", "Téléphone", "Agence"),
        rows,
    )


@login_required
@never_cache
def client_ajouter(request):
    user = request.user
    if request.method == "POST":
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save(commit=False)
            # Si non-superuser, on force l'agence de l'employé connecté
            if not user.is_superuser:
                try:
                    client.agence = user.profil.agence
                except AttributeError:
                    pass
            client.save()
            return redirect("core:liste_clients")
    else:
        form = ClientForm()
        # Restreindre le choix de l'agence pour un employé simple
        if not user.is_superuser:
            try:
                form.fields["agence"].queryset = Agence.objects.filter(
                    id=user.profil.agence.id
                )
                form.initial["agence"] = user.profil.agence
            except AttributeError:
                pass

    return render(
        request, "core/pages/client_form.html", {"form": form, "action": "Ajouter"}
    )


@login_required
@never_cache
def client_modifier(request, pk):
    client = get_object_or_404(Client, pk=pk)
    user = request.user

    # Contrôle d'accès agence
    if not user.is_superuser:
        try:
            if client.agence != user.profil.agence:
                return redirect("core:liste_clients")
        except AttributeError:
            return redirect("core:liste_clients")

    if request.method == "POST":
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            return redirect("core:liste_clients")
    else:
        form = ClientForm(instance=client)
        if not user.is_superuser:
            try:
                form.fields["agence"].queryset = Agence.objects.filter(
                    id=user.profil.agence.id
                )
            except AttributeError:
                pass

    return render(
        request,
        "core/pages/client_form.html",
        {"form": form, "client": client, "action": "Modifier"},
    )


@login_required
@never_cache
def client_supprimer(request, pk):
    client = get_object_or_404(Client, pk=pk)

    # 🔒 Vérifier si le client a des locations via le modèle Location directement
    if Location.objects.filter(client=client).exists():
        messages.error(
            request,
            f"Impossible de supprimer le client {client.nom} {client.prenom} car il a déjà effectué une ou plusieurs locations.",
        )
        return redirect("core:liste_clients")

    if request.method == "POST":
        client.delete()
        messages.success(request, "Le client a été supprimé avec succès.")
        return redirect("core:liste_clients")

    return redirect("core:liste_clients")


# Utilisateurs : liste, ajout, modification, suppression
@login_required
@never_cache
def liste_utilisateurs(request):
    if not request.user.is_superuser:
        return redirect("core:dashboard")

    query = request.GET.get("q", "")
    sort_by = request.GET.get("sort", "-id")

    utilisateurs = User.objects.all()

    # Recherche dynamique (Nom, Prénom, Email, Login)
    if query:
        utilisateurs = utilisateurs.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        )

    # Dictionnaire des tris autorisés
    allowed_sorts = {
        "nom": "last_name",
        "-nom": "-last_name",
        "prenom": "first_name",
        "-prenom": "-first_name",
        "email": "email",
        "-email": "-email",
        "agence": "profil__agence__nom",
        "-agence": "-profil__agence__nom",
        "username": "username",
        "-username": "-username",
    }

    if sort_by in allowed_sorts:
        utilisateurs = utilisateurs.order_by(allowed_sorts[sort_by])
    else:
        utilisateurs = utilisateurs.order_by("-id")

    # Pagination (10 utilisateurs par page)
    paginator = Paginator(utilisateurs, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "utilisateurs": page_obj,
        "query": query,
        "current_sort": sort_by,
    }
    return render(request, "core/pages/liste_utilisateurs.html", context)


@login_required
@never_cache
def exporter_utilisateurs_csv(request):
    if not request.user.is_superuser:
        return redirect("core:dashboard")

    utilisateurs = User.objects.select_related("profil__agence").order_by("pk")
    rows = (
        (
            utilisateur.pk,
            utilisateur.first_name,
            utilisateur.last_name,
            utilisateur.username,
            utilisateur.email,
            (
                utilisateur.profil.agence.nom
                if hasattr(utilisateur, "profil") and utilisateur.profil.agence
                else ""
            ),
            "Oui" if utilisateur.is_active else "Non",
            timezone.localtime(utilisateur.date_joined).strftime("%d/%m/%Y %H:%M"),
        )
        for utilisateur in utilisateurs
    )
    return _csv_response(
        "utilisateurs.csv",
        (
            "#ID",
            "Prénom",
            "Nom",
            "Identifiant",
            "Email",
            "Agence",
            "Actif",
            "Date de création",
        ),
        rows,
    )


@login_required
@never_cache
def utilisateur_modifier(request, pk):
    if not request.user.is_superuser:
        return redirect("core:dashboard")

    user_obj = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        form = AdminUserForm(request.POST, instance=user_obj)
        if form.is_valid():
            form.save()
            return redirect("core:liste_utilisateurs")
    else:
        form = AdminUserForm(instance=user_obj)

    context = {
        "form": form,
        "utilisateur": user_obj,
    }
    return render(request, "core/pages/utilisateur_form.html", context)


@login_required
@never_cache
def utilisateur_toggle_status(request, pk):
    if not request.user.is_superuser:
        return redirect("core:dashboard")

    user_obj = get_object_or_404(User, pk=pk)
    # Empêcher l'admin de se désactiver lui-même par erreur
    if user_obj != request.user:
        user_obj.is_active = not user_obj.is_active
        user_obj.save()

    return redirect("core:liste_utilisateurs")


@login_required
@never_cache
def mon_profil(request):
    user = request.user
    if request.method == "POST":
        form = UserProfileForm(request.POST, instance=user)
        password_form = PasswordChangeForm(user, request.POST)

        # Gestion de la soumission simultanée ou séparée (ici on gère les deux formulaires)
        if "update_profile" in request.POST and form.is_valid():
            form.save()
            return redirect("core:mon_profil")

        elif "update_password" in request.POST:
            if password_form.is_valid():
                user_updated = password_form.save()
                update_session_auth_hash(request, user_updated)  # Évite la déconnexion
                return redirect("core:mon_profil")
    else:
        form = UserProfileForm(instance=user)
        password_form = PasswordChangeForm(user)

    context = {
        "form": form,
        "password_form": password_form,
    }
    return render(request, "core/pages/mon_profil.html", context)


# Categories : liste, ajout, modification, suppression
@login_required
@never_cache
def liste_categories(request):
    if not request.user.is_superuser:
        return redirect("core:dashboard")

    categories = Categorie.objects.all().order_by("nom")
    context = {"categories": categories}
    return render(request, "core/pages/liste_categories.html", context)


@login_required
@never_cache
def categorie_ajouter(request):
    if not request.user.is_superuser:
        return redirect("core:dashboard")

    if request.method == "POST":
        form = CategorieForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("core:liste_categories")
    else:
        form = CategorieForm()

    return render(
        request, "core/pages/categorie_form.html", {"form": form, "action": "Ajouter"}
    )


@login_required
@never_cache
def categorie_modifier(request, pk):
    if not request.user.is_superuser:
        return redirect("core:dashboard")

    categorie = get_object_or_404(Categorie, pk=pk)
    if request.method == "POST":
        form = CategorieForm(request.POST, instance=categorie)
        if form.is_valid():
            form.save()
            return redirect("core:liste_categories")
    else:
        form = CategorieForm(instance=categorie)

    return render(
        request,
        "core/pages/categorie_form.html",
        {"form": form, "categorie": categorie, "action": "Modifier"},
    )


@login_required
@never_cache
def categorie_supprimer(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Seul un administrateur peut supprimer une catégorie.")
        return redirect("core:dashboard")
    if request.method != "POST":
        messages.error(
            request, "La suppression doit être confirmée depuis le formulaire."
        )
        return redirect("core:liste_categories")

    with transaction.atomic():
        categorie = get_object_or_404(
            Categorie.objects.select_for_update(), pk=pk
        )
        if categorie.equipements.exists():
            messages.error(
                request,
                f"Impossible de supprimer la catégorie « {categorie.nom} » : elle contient encore des équipements.",
            )
        else:
            categorie.delete()
            messages.success(request, "La catégorie a été supprimée avec succès.")

    return redirect("core:liste_categories")


# Agences : liste, ajout, modification, suppression
@login_required
@never_cache
def liste_agences(request):
    agences = Agence.objects.all()
    return render(request, "core/pages/liste_agences.html", {"agences": agences})


@login_required
@never_cache
def exporter_agences_csv(request):
    agences = Agence.objects.order_by("pk")
    rows = (
        (agence.pk, agence.nom, agence.ville, agence.adresse)
        for agence in agences
    )
    return _csv_response(
        "agences.csv", ("#ID", "Nom", "Ville", "Adresse"), rows
    )


@login_required
@never_cache
def agence_ajouter(request):
    if request.method == "POST":
        form = AgenceForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "L'agence a été créée avec succès.")
            return redirect("core:liste_agences")
    else:
        form = AgenceForm()
    return render(
        request, "core/pages/agence_form.html", {"form": form, "action": "Ajouter"}
    )


@login_required
@never_cache
def agence_modifier(request, pk):
    agence = get_object_or_404(Agence, pk=pk)
    if request.method == "POST":
        form = AgenceForm(request.POST, instance=agence)
        if form.is_valid():
            form.save()
            messages.success(request, "L'agence a été modifiée avec succès.")
            return redirect("core:liste_agences")
    else:
        form = AgenceForm(instance=agence)
    return render(
        request, "core/pages/agence_form.html", {"form": form, "action": "Modifier"}
    )


@login_required
@never_cache
def agence_supprimer(request, pk):
    agence = get_object_or_404(Agence, pk=pk)

    # Sécurité stricte basée sur la méthode du modèle
    if agence.a_des_dependances():
        messages.error(
            request,
            f"Action impossible : L'agence « {agence.nom} » possède des données liées (clients, équipements, utilisateurs ou locations) et ne peut pas être supprimée.",
        )
    else:
        agence.delete()
        messages.success(request, "L'agence a été supprimée avec succès.")

    return redirect("core:liste_agences")


# Locations : liste, ajout, modification, suppression
@login_required
@never_cache
def creer_location(request):
    user = request.user
    client_agence_map = dict(Client.objects.values_list("id", "agence_id"))

    agence_cible = None
    if request.method == "POST":
        agence_id_post = request.POST.get("agence")
        if agence_id_post:
            try:
                agence_cible = Agence.objects.filter(pk=int(agence_id_post)).first()
            except (TypeError, ValueError):
                agence_cible = None

    if not agence_cible and not user.is_superuser:
        try:
            agence_cible = user.profil.agence
        except AttributeError:
            pass

    equipements_loues_ids = LocationEquipement.objects.filter(
        location__retour_reelle__isnull=True,
        location__statut__in=("en_cours", "etendue", "retard"),
    ).values_list("equipement_id", flat=True)
    equipements_tous = Equipement.objects.filter(statut="disponible").exclude(
        id__in=equipements_loues_ids
    )
    if agence_cible:
        equipements_tous = equipements_tous.filter(agence=agence_cible)
    elif not user.is_superuser:
        equipements_tous = equipements_tous.none()
    equipements_tous = equipements_tous.select_related("agence")

    if request.method == "POST":
        form = LocationForm(request.POST, user=user)
        try:
            equipements_ids = list(
                dict.fromkeys(
                    int(value) for value in request.POST.getlist("equipements")
                )
            )
        except (TypeError, ValueError):
            equipements_ids = []
            messages.error(request, "La sélection d'équipements est invalide.")

        if form.is_valid() and equipements_ids:
            if not user.is_superuser and not agence_cible:
                messages.error(request, "Votre compte n'est rattaché à aucune agence.")
            else:
                with transaction.atomic():
                    location = form.save(commit=False)
                    if not user.is_superuser:
                        location.agence = agence_cible
                    location.employe = user

                    equipements = list(
                        Equipement.objects.select_for_update()
                        .filter(pk__in=equipements_ids)
                        .order_by("pk")
                    )
                    conflit = LocationEquipement.objects.filter(
                        equipement_id__in=equipements_ids,
                        location__retour_reelle__isnull=True,
                        location__statut__in=("en_cours", "etendue", "retard"),
                    ).exists()
                    equipements_valides = (
                        len(equipements) == len(equipements_ids)
                        and all(
                            equipement.agence_id == location.agence_id
                            and equipement.statut == "disponible"
                            for equipement in equipements
                        )
                        and not conflit
                    )

                    if not equipements_valides:
                        messages.error(
                            request,
                            "Un équipement n'est plus disponible, n'appartient pas à cette agence ou est en maintenance. Actualisez la sélection.",
                        )
                    else:
                        duree = (location.retour_prevue - location.date_debut).days
                        location.montant_total = _prix_location(equipements, duree)
                        location.caution = _arrondir_montant(
                            location.montant_total * Decimal("0.50")
                        )
                        location.save()

                        LocationEquipement.objects.bulk_create(
                            [
                                LocationEquipement(
                                    location=location,
                                    equipement=equipement,
                                    prix_journalier_applique=equipement.prix_journalier,
                                )
                                for equipement in equipements
                            ]
                        )
                        Equipement.objects.filter(
                            pk__in=equipements_ids
                        ).update(statut="loue")

                        notify_location_event(
                            location,
                            user,
                            "location_created",
                            "Nouvelle location enregistrée",
                            (
                                f"La location #{location.pk} pour "
                                f"{location.client} a été créée. "
                                f"Retour prévu le {location.retour_prevue:%d/%m/%Y}."
                            ),
                        )
                        messages.success(
                            request, f"La location #{location.id} a été créée avec succès."
                        )
                        return redirect("core:liste_locations")
        else:
            if not equipements_ids:
                messages.error(
                    request,
                    "Veuillez sélectionner au moins un équipement pour cette location.",
                )
    else:
        form = LocationForm(user=user)

    return render(
        request,
        "core/pages/location_form.html",
        {
            "form": form,
            "equipements_tous": equipements_tous,
            "client_agence_map": client_agence_map,
            "action": "Créer",
        },
    )


@login_required
@never_cache
def liste_locations(request):
    user = request.user
    if user.is_superuser:
        locations = Location.objects.all()
    else:
        try:
            agence_employe = user.profil.agence
            locations = Location.objects.filter(agence=agence_employe)
        except AttributeError:
            locations = Location.objects.none()

    # locations = locations.select_related(
    #     "client", "agence", "employe"
    # ).prefetch_related("lignes_location__equipement")
    locations = locations.order_by('-date_creation')

    return render(request, "core/pages/liste_locations.html", {"locations": locations})


@login_required
@never_cache
def exporter_locations_csv(request):
    locations = _agence_queryset_for_user(
        request.user,
        Location.objects.select_related("client", "agence")
        .order_by("pk"),
    )
    aujourd_hui = timezone.localdate()
    rows = []
    for location in locations:
        remboursement, montant_final = _montants_location_csv(
            location, aujourd_hui
        )
        periode = (
            f"Du {location.date_debut:%d/%m/%Y} "
            f"au {location.retour_prevue:%d/%m/%Y}"
        )
        rows.append(
            (
                location.pk,
                f"{location.client.prenom or ''} {location.client.nom}".strip(),
                location.agence.nom,
                periode,
                location.montant_total,
                remboursement,
                location.caution,
                montant_final,
            )
        )
    return _csv_response(
        "locations.csv",
        (
            "#ID",
            "Client",
            "Agence",
            "Période",
            "Montant Total",
            "Remboursement",
            "Caution déposée",
            "Montant Final",
        ),
        rows,
    )


@login_required
@never_cache
def detail_location(request, pk):
    """
    Affiche le détail complet d'une location, ses équipements et ses montants financiers.
    """
    location = get_object_or_404(
        Location.objects.select_related("client", "agence", "employe").prefetch_related(
            "lignes_location__equipement"
        ),
        pk=pk,
    )
    user = request.user

    # Sécurité agence pour les simples employés
    if not user.is_superuser:
        try:
            if location.agence != user.profil.agence:
                return redirect("core:liste_locations")
        except AttributeError:
            return redirect("core:liste_locations")

    return render(
        request,
        "core/pages/location_detail.html",
        {
            "location": location,
            "prolongation_form": ProlongationLocationForm(),
            "renttech_name": RENTTECH_NAME,
            "renttech_description": RENTTECH_DESCRIPTION,
        },
    )


@login_required
@never_cache
def telecharger_location_pdf(request, pk):
    location = get_object_or_404(
        Location.objects.select_related("client", "agence", "employe").prefetch_related(
            "lignes_location__equipement"
        ),
        pk=pk,
    )
    user = request.user

    if not user.is_superuser:
        try:
            if location.agence != user.profil.agence:
                return redirect("core:liste_locations")
        except AttributeError:
            return redirect("core:liste_locations")

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )
    styles = getSampleStyleSheet()
    logo_path = finders.find("core/images/RentTech_Logo.jpg")
    if logo_path is None:
        raise FileNotFoundError(
            "Logo RentTech introuvable dans les fichiers statiques."
        )

    company_header = Table(
        [
            [
                Image(logo_path, width=28 * mm, height=28 * mm, kind="proportional"),
                [
                    Paragraph(RENTTECH_NAME, styles["Heading1"]),
                    Paragraph(RENTTECH_DESCRIPTION, styles["BodyText"]),
                ],
            ]
        ],
        colWidths=[35 * mm, 135 * mm],
    )
    company_header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    retour_reel = (
        location.retour_reelle.strftime("%d/%m/%Y")
        if location.retour_reelle
        else "N/A"
    )
    statut_labels = {
        "en_cours": "En cours",
        "etendue": "Étendue",
        "terminee": "Terminée",
        "retard": "En retard",
        "annulee": "Annulée",
    }
    elements = [
        company_header,
        Spacer(1, 8 * mm),
        Paragraph(f"Contrat de location #{location.id}", styles["Title"]),
        Spacer(1, 8 * mm),
        Paragraph(
            f"Agence : {escape(location.agence.nom)}<br/>"
            f"Créé par : {escape(location.employe.username if location.employe else 'N/A')}<br/>"
            f"Statut : {statut_labels.get(location.statut, 'N/A')}",
            styles["BodyText"],
        ),
        Spacer(1, 5 * mm),
        Paragraph("Informations client", styles["Heading2"]),
        Paragraph(
            f"{escape(location.client.nom)} {escape(location.client.prenom or '')}<br/>"
            f"Email : {escape(location.client.email or 'N/A')}<br/>"
            f"Téléphone : {escape(location.client.telephone or 'N/A')}",
            styles["BodyText"],
        ),
        Spacer(1, 5 * mm),
        Paragraph("Période de location", styles["Heading2"]),
        Paragraph(
            f"Début : {location.date_debut:%d/%m/%Y}<br/>"
            f"Retour prévu : {location.retour_prevue:%d/%m/%Y}<br/>"
            f"Retour réel : {retour_reel}",
            styles["BodyText"],
        ),
        Spacer(1, 5 * mm),
        Paragraph("Équipements loués", styles["Heading2"]),
    ]

    equipment_rows = [["Référence & nom", "Prix journalier appliqué"]]
    equipment_rows.extend(
        [
            [
                Paragraph(
                    f"{escape(ligne.equipement.nom)} "
                    f"({escape(ligne.equipement.reference)})",
                    styles["BodyText"],
                ),
                f"{ligne.prix_journalier_applique} € / jour",
            ]
            for ligne in location.lignes_location.all()
        ]
    )
    equipment_table = Table(equipment_rows, colWidths=[95 * mm, 75 * mm], repeatRows=1)
    equipment_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#374151")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    recapitulatif = (
        f"Montant total de la location : {location.montant_total} €<br/>"
        f"Pénalité de retard (10 % par jour) : {location.penalite_retard} €<br/>"
        f"Caution (50 %) : {location.caution} €"
    )
    if location.statut == "annulee":
        recapitulatif += (
            f"<br/><br/><b>Annulation — remboursement à effectuer</b><br/>"
            f"Loyer remboursé au client (90 %) : "
            f"{location.montant_loyer_a_rembourser} €<br/>"
            f"Loyer conservé par l'agence (10 %) : "
            f"{location.montant_loyer_conserve} €<br/>"
            f"Caution remboursée intégralement : "
            f"{location.montant_caution_a_rembourser} €<br/>"
            f"Total à rembourser au client : "
            f"{location.montant_total_a_rembourser} €"
        )
    elif location.retour_reelle or location.statut == "terminee":
        recapitulatif += (
            f"<br/><br/><b>Clôture — remboursement à effectuer</b><br/>"
            f"Loyer remboursé au client : "
            f"{location.montant_loyer_a_rembourser} € "
            "(aucun remboursement du loyer après le début de la location)<br/>"
            f"Caution restante après imputation des pénalités : "
            f"{location.montant_caution_a_rembourser} €<br/>"
            f"Total à rembourser au client : "
            f"{location.montant_total_a_rembourser} €"
        )

    elements.extend(
        [
            equipment_table,
            Spacer(1, 8 * mm),
            Paragraph("Récapitulatif financier", styles["Heading2"]),
            Paragraph(recapitulatif, styles["BodyText"]),
        ]
    )
    document.build(elements)

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="location-{location.id}.pdf"'
    )
    return response


@login_required
@never_cache
def modifier_location(request, pk):
    location = get_object_or_404(Location, pk=pk)
    user = request.user

    if not user.is_superuser:
        messages.error(request, "Seul un administrateur peut modifier une location.")
        return redirect("core:liste_locations")
    if _location_est_cloturee(location):
        messages.error(request, "Une location clôturée ou annulée ne peut plus être modifiée.")
        return redirect("core:liste_locations")

    client_agence_map = dict(Client.objects.values_list("id", "agence_id"))

    if request.method == "POST":
        form = LocationForm(request.POST, instance=location, user=user)
        try:
            equipements_ids = list(
                dict.fromkeys(
                    int(value) for value in request.POST.getlist("equipements")
                )
            )
        except (TypeError, ValueError):
            equipements_ids = []
            messages.error(request, "La sélection d'équipements est invalide.")

        if form.is_valid() and equipements_ids:
            with transaction.atomic():
                location = get_object_or_404(
                    Location.objects.select_for_update(), pk=pk
                )
                if _location_est_cloturee(location):
                    messages.error(
                        request,
                        "Une location clôturée ou annulée ne peut plus être modifiée.",
                    )
                    return redirect("core:liste_locations")
                form = LocationForm(request.POST, instance=location, user=user)
                if not form.is_valid():
                    messages.error(
                        request,
                        "Les données de la location ont changé. Vérifiez le formulaire puis réessayez.",
                    )
                    return redirect("core:liste_locations")

                anciennes_lignes = list(location.lignes_location.all())
                anciens_ids = {ligne.equipement_id for ligne in anciennes_lignes}
                tous_ids = sorted(anciens_ids | set(equipements_ids))
                equipements_verrouilles = list(
                    Equipement.objects.select_for_update()
                    .filter(pk__in=tous_ids)
                    .order_by("pk")
                )
                equipements_par_id = {
                    equipement.pk: equipement for equipement in equipements_verrouilles
                }

                conflits = LocationEquipement.objects.filter(
                    equipement_id__in=equipements_ids,
                    location__retour_reelle__isnull=True,
                    location__statut__in=("en_cours", "etendue", "retard"),
                ).exclude(location=location).exists()
                equipements_valides = (
                    len(equipements_par_id) == len(tous_ids)
                    and all(
                        equipements_par_id[equipement_id].agence_id
                        == form.cleaned_data["agence"].id
                        and (
                            equipements_par_id[equipement_id].statut == "disponible"
                            or (
                                equipement_id in anciens_ids
                                and equipements_par_id[equipement_id].statut == "loue"
                            )
                        )
                        for equipement_id in equipements_ids
                    )
                    and not conflits
                )

                if not equipements_valides:
                    messages.error(
                        request,
                        "Un équipement n'est plus disponible, n'appartient pas à cette agence ou est en maintenance. Aucun changement n'a été enregistré.",
                    )
                else:
                    loc_modifiee = form.save(commit=False)
                    duree = (loc_modifiee.retour_prevue - loc_modifiee.date_debut).days
                    equipements_selectionnes = [
                        equipements_par_id[equipement_id]
                        for equipement_id in equipements_ids
                    ]
                    loc_modifiee.montant_total = _prix_location(
                        equipements_selectionnes, duree
                    )
                    loc_modifiee.caution = _arrondir_montant(
                        loc_modifiee.montant_total * Decimal("0.50")
                    )
                    loc_modifiee.save()

                    location.lignes_location.all().delete()
                    equipements_loues_ailleurs = LocationEquipement.objects.filter(
                        equipement_id__in=anciens_ids,
                        location__retour_reelle__isnull=True,
                        location__statut__in=("en_cours", "etendue", "retard"),
                    ).exclude(location=location).values_list(
                        "equipement_id", flat=True
                    )
                    Equipement.objects.filter(
                        pk__in=anciens_ids, statut="loue"
                    ).exclude(
                        pk__in=equipements_loues_ailleurs
                    ).update(statut="disponible")
                    LocationEquipement.objects.bulk_create(
                        [
                            LocationEquipement(
                                location=loc_modifiee,
                                equipement=equipement,
                                prix_journalier_applique=equipement.prix_journalier,
                            )
                            for equipement in equipements_selectionnes
                        ]
                    )
                    Equipement.objects.filter(
                        pk__in=equipements_ids
                    ).update(statut="loue")

                    notify_location_event(
                        loc_modifiee,
                        user,
                        "location_updated",
                        "Location modifiée",
                        (
                            f"La location #{loc_modifiee.pk} de "
                            f"{loc_modifiee.client} a été modifiée. "
                            f"Retour prévu le {loc_modifiee.retour_prevue:%d/%m/%Y}."
                        ),
                    )
                    messages.success(
                        request,
                        f"La location #{location.id} a été modifiée avec succès.",
                    )
                    return redirect("core:liste_locations")
        else:
            if not equipements_ids:
                messages.error(request, "Veuillez sélectionner au moins un équipement.")
    else:
        form = LocationForm(instance=location, user=user)

    # Récupérer les équipements disponibles (en excluant les autres locations en cours, mais en gardant ceux de CETte location)
    equipements_actuels_ids = list(
        location.lignes_location.values_list("equipement_id", flat=True)
    )
    equipements_autres_loues = (
        LocationEquipement.objects.filter(
            location__retour_reelle__isnull=True,
            location__statut__in=("en_cours", "etendue", "retard"),
        )
        .exclude(location=location)
        .values_list("equipement_id", flat=True)
    )

    equipements_tous = Equipement.objects.filter(
        Q(statut="disponible") | Q(pk__in=equipements_actuels_ids)
    ).exclude(id__in=equipements_autres_loues).select_related("agence")

    return render(
        request,
        "core/pages/location_form.html",
        {
            "form": form,
            "equipements_tous": equipements_tous,
            "client_agence_map": client_agence_map,
            "location": location,
            "equipements_actuels_ids": equipements_actuels_ids,
            "action": "Modifier",
        },
    )


@login_required
@never_cache
def annuler_location(request, pk):
    if request.method != "POST":
        return redirect("core:liste_locations")

    user = request.user
    with transaction.atomic():
        location = get_object_or_404(
            Location.objects.select_for_update(), pk=pk
        )
        if not _location_accessible(user, location):
            messages.error(request, "Accès non autorisé.")
            return redirect("core:liste_locations")
        if not location.est_annulable:
            messages.error(
                request,
                "Impossible d'annuler cette location : le délai de 24 heures est dépassé ou le contrat est déjà clôturé/annulé.",
            )
            return redirect("core:liste_locations")

        equipements_ids = list(
            location.lignes_location.values_list("equipement_id", flat=True)
        )
        list(
            Equipement.objects.select_for_update()
            .filter(pk__in=equipements_ids)
            .order_by("pk")
        )
        for equipement_id in equipements_ids:
            has_other_active_location = LocationEquipement.objects.filter(
                equipement_id=equipement_id,
                location__retour_reelle__isnull=True,
                location__statut__in=("en_cours", "etendue", "retard"),
            ).exclude(location=location).exists()
            if not has_other_active_location:
                Equipement.objects.filter(
                    pk=equipement_id, statut="loue"
                ).update(statut="disponible")
        location.statut = "annulee"
        location.save(update_fields=["statut"])
        notify_location_event(
            location,
            user,
            "location_cancelled",
            "Location annulée",
            (
                f"La location #{location.pk} de {location.client} a été annulée. "
                f"Remboursement total à effectuer : "
                f"{location.montant_total_a_rembourser} €."
            ),
        )
        messages.success(
            request,
            f"La location #{location.id} a été annulée. Remboursement à effectuer : "
            f"{location.montant_loyer_a_rembourser} € sur le loyer (90 %) + "
            f"{location.montant_caution_a_rembourser} € de caution. "
            f"Part du loyer conservée par l'agence : {location.montant_loyer_conserve} €.",
        )
    return redirect("core:liste_locations")


@login_required
@never_cache
def supprimer_location(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Seul un administrateur peut supprimer une location.")
        return redirect("core:liste_locations")
    if request.method != "POST":
        return redirect("core:liste_locations")

    with transaction.atomic():
        location = get_object_or_404(
            Location.objects.select_for_update(), pk=pk
        )
        if _location_est_cloturee(location):
            messages.error(
                request,
                "Une location clôturée ou annulée ne peut plus être supprimée.",
            )
            return redirect("core:liste_locations")

        equipements_ids = list(
            location.lignes_location.values_list("equipement_id", flat=True)
        )
        list(
            Equipement.objects.select_for_update()
            .filter(pk__in=equipements_ids)
            .order_by("pk")
        )
        equipements_loues_ailleurs = LocationEquipement.objects.filter(
            equipement_id__in=equipements_ids,
            location__retour_reelle__isnull=True,
            location__statut__in=("en_cours", "etendue", "retard"),
        ).exclude(location=location).values_list("equipement_id", flat=True)
        Equipement.objects.filter(
            pk__in=equipements_ids, statut="loue"
        ).exclude(pk__in=equipements_loues_ailleurs).update(
            statut="disponible"
        )
        notification_location = location
        notify_location_event(
            notification_location,
            request.user,
            "location_deleted",
            "Location supprimée",
            (
                f"La location #{notification_location.pk} de "
                f"{notification_location.client} a été supprimée."
            ),
            target_url=reverse("core:liste_locations"),
        )
        location.delete()
        messages.success(
            request,
            "La location a été supprimée et ses équipements actifs ont été libérés.",
        )
    return redirect("core:liste_locations")


@login_required
@never_cache
def retourner_location(request, pk):
    if request.method != "POST":
        return redirect("core:detail_location", pk=pk)

    with transaction.atomic():
        location = get_object_or_404(
            Location.objects.select_for_update(), pk=pk
        )
        if not _location_accessible(request.user, location):
            messages.error(request, "Accès non autorisé.")
            return redirect("core:liste_locations")
        if location.statut == "annulee":
            messages.error(request, "Une location annulée ne peut pas être clôturée.")
            return redirect("core:liste_locations")
        if location.retour_reelle or location.statut == "terminee":
            messages.warning(
                request, f"La location #{location.id} est déjà clôturée."
            )
            return redirect("core:liste_locations")

        equipements_ids = list(
            location.lignes_location.values_list("equipement_id", flat=True)
        )
        list(
            Equipement.objects.select_for_update()
            .filter(pk__in=equipements_ids)
            .order_by("pk")
        )
        location.retour_reelle = timezone.localdate()
        location.statut = "terminee"
        location.penalite_retard += location.calculer_penalite_retard(
            location.retour_reelle
        )
        location.save(
            update_fields=["retour_reelle", "statut", "penalite_retard"]
        )

        for equipement_id in equipements_ids:
            has_other_active_location = LocationEquipement.objects.filter(
                equipement_id=equipement_id,
                location__retour_reelle__isnull=True,
                location__statut__in=("en_cours", "etendue", "retard"),
            ).exclude(location=location).exists()
            if not has_other_active_location:
                Equipement.objects.filter(
                    pk=equipement_id, statut="loue"
                ).update(statut="disponible")

        notify_location_event(
            location,
            request.user,
            "location_returned",
            "Location clôturée",
            (
                f"Le retour de la location #{location.pk} de {location.client} "
                f"a été enregistré le {location.retour_reelle:%d/%m/%Y}. "
                f"Pénalités enregistrées : {location.penalite_retard} €."
            ),
        )
        messages.success(
            request,
            f"La location #{location.id} est clôturée. Les équipements disponibles ont été libérés. "
            f"Pénalités imputées sur la caution : {location.penalite_retard} €. "
            f"Caution restante à rembourser : {location.montant_caution_a_rembourser} €. "
            "Aucun remboursement du loyer.",
        )
    return redirect("core:liste_locations")


@login_required
@never_cache
def etendre_location(request, pk):
    location = get_object_or_404(Location, pk=pk)
    if not _location_accessible(request.user, location):
        messages.error(request, "Accès non autorisé.")
        return redirect("core:liste_locations")
    if request.method != "POST":
        return redirect("core:detail_location", pk=pk)

    form = ProlongationLocationForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Veuillez saisir une date de retour valide.")
        return redirect("core:detail_location", pk=pk)

    with transaction.atomic():
        location = get_object_or_404(
            Location.objects.select_for_update(), pk=pk
        )
        if not _location_accessible(request.user, location):
            messages.error(request, "Accès non autorisé.")
            return redirect("core:liste_locations")
        if not location.est_active:
            messages.error(
                request, "Seule une location active peut être prolongée."
            )
            return redirect("core:detail_location", pk=pk)

        nouvelle_date = form.cleaned_data["nouvelle_date"]
        if nouvelle_date <= location.retour_prevue:
            messages.error(
                request,
                "La nouvelle date de retour doit être postérieure à l'échéance actuelle.",
            )
            return redirect("core:detail_location", pk=pk)

        lignes = list(
            location.lignes_location.select_related("equipement").all()
        )
        if not lignes:
            messages.error(
                request,
                "La location ne contient aucun équipement et ne peut pas être prolongée.",
            )
            return redirect("core:detail_location", pk=pk)

        ancienne_date = location.retour_prevue
        aujourd_hui = timezone.localdate()
        penalite_accrue = location.calculer_penalite_retard(aujourd_hui)
        jours_supplementaires = (nouvelle_date - ancienne_date).days
        montant_supplementaire = (
            sum(
                (
                    ligne.prix_journalier_applique
                    for ligne in lignes
                ),
                Decimal("0.00"),
            )
            * jours_supplementaires
        ).quantize(Decimal("0.01"))

        location.retour_prevue = nouvelle_date
        location.montant_total += montant_supplementaire
        location.penalite_retard += penalite_accrue
        location.caution = _arrondir_montant(
            location.montant_total * Decimal("0.50")
        )
        location.statut = "etendue"
        location.save(
            update_fields=[
                "retour_prevue",
                "montant_total",
                "penalite_retard",
                "caution",
                "statut",
            ]
        )
        ProlongationLocation.objects.create(
            location=location,
            ancienne_date=ancienne_date,
            nouvelle_date=nouvelle_date,
            montant_supplementaire=montant_supplementaire,
            employe=request.user,
        )
        notify_location_event(
            location,
            request.user,
            "location_extended",
            "Location prolongée",
            (
                f"La location #{location.pk} de {location.client} a été prolongée "
                f"jusqu’au {location.retour_prevue:%d/%m/%Y}. "
                f"Supplément : {montant_supplementaire} €."
            ),
        )
        messages.success(
            request,
            f"La location #{location.id} est prolongée jusqu'au {nouvelle_date:%d/%m/%Y}. "
            f"Supplément de location : {montant_supplementaire} €. "
            f"Pénalité de retard ajoutée : {penalite_accrue} €.",
        )
    return redirect("core:detail_location", pk=pk)
