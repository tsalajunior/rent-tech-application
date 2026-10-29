from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User

from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.db import transaction
from .models import (
    Agence,
    Categorie,
    Equipement,
    Client,
    Location,
    LocationEquipement,
    ProfilEmploye,
)
from django.views.decorators.cache import never_cache
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from .forms import (
    ClientForm,
    EquipementForm,
    AdminUserForm,
    UserProfileForm,
    CategorieForm,
    AgenceForm,
    LocationForm,
)


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
        locations_en_cours = Location.objects.filter(retour_reelle__isnull=True).count()
        agence_libelle = "Administration Centrale (Vue globale)"
    else:
        try:
            employe_agence = user.profil.agence
            # Filtrage strict par agence pour l'employé
            total_equipements = Equipement.objects.filter(agence=employe_agence).count()
            total_clients = Client.objects.filter(agence=employe_agence).count()
            locations_en_cours = Location.objects.filter(
                agence=employe_agence, retour_reelle__isnull=True
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
def equipement_ajouter(request):
    # Réservé exclusivement à l'administrateur central
    if not request.user.is_superuser:
        return redirect("core:liste_equipements")

    if request.method == "POST":
        form = EquipementForm(request.POST)
        if form.is_valid():
            form.save()
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

    equipement = get_object_or_404(Equipement, pk=pk)

    if request.method == "POST":
        equipement.delete()
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

    equipement = get_object_or_404(Equipement, pk=pk)

    if request.method == "POST":
        form = EquipementForm(request.POST, instance=equipement)
        if form.is_valid():
            form.save()
            return redirect("core:liste_equipements")
    else:
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
    }
    return render(request, "core/pages/liste_clients.html", context)


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
    if not request.user.is_superuser:
        return redirect("core:liste_clients")

    client = get_object_or_404(Client, pk=pk)
    if request.method == "POST":
        client.delete()
        return redirect("core:liste_clients")

    return render(
        request, "core/pages/client_confirmer_suppression.html", {"client": client}
    )


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
    categorie = get_object_or_404(Categorie, pk=pk)

    # Vérifie si des équipements sont liés à cette catégorie
    # (Note : si vous avez défini un 'related_name' dans votre modèle Equipement, remplacez 'equipement_set' par ce nom)
    if categorie.equipements.exists():
        messages.error(
            request,
            f"Impossible de supprimer la catégorie « {categorie.nom} » car elle est associée à un ou plusieurs équipements.",
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

    # Récupérer les IDs des équipements actuellement engagés dans une location en cours (non retournés)
    equipements_loues_ids = LocationEquipement.objects.filter(
        location__retour_reelle__isnull=True
    ).values_list("equipement_id", flat=True)

    # Filtrer les équipements disponibles :
    # - Selon l'agence (si non-superuser)
    # - Exclure ceux qui sont déjà loués (retour_reelle IS NULL)
    # - Exclure ceux qui sont en maintenance ou indisponibles (ajuste selon les valeurs de ton champ statut, ex: 'disponible')
    if user.is_superuser:
        equipements_qs = Equipement.objects.exclude(id__in=equipements_loues_ids)
    else:
        try:
            equipements_qs = Equipement.objects.filter(
                agence=user.profil.agence
            ).exclude(id__in=equipements_loues_ids)
        except AttributeError:
            equipements_qs = Equipement.objects.none()

    # Si tu as un champ 'statut' sur ton modèle Equipement (ex: statut='disponible'), tu peux affiner ainsi :
    # equipements_qs = equipements_qs.filter(statut='disponible')

    # Dictionnaire des prix pour le JS
    equipements_prix = {
        str(eq.id): float(getattr(eq, "prix_journalier", 0.00)) for eq in equipements_qs
    }

    if request.method == "POST":
        form = LocationForm(request.POST, user=user)
        equipements_ids = request.POST.getlist("equipements")

        if form.is_valid() and equipements_ids:
            try:
                with transaction.atomic():
                    # Double sécurité : vérifier au moment du POST qu'aucun équipement n'a été loué entretemps
                    conflit = LocationEquipement.objects.filter(
                        equipement_id__in=equipements_ids,
                        location__retour_reelle__isnull=True,
                    ).exists()

                    if conflit:
                        messages.error(
                            request,
                            "Un ou plusieurs équipements sélectionnés viennent d'être loués par un autre contrat. Veuillez actualiser votre sélection.",
                        )
                        return redirect("core:creer_location")

                    location = form.save(commit=False)
                    location.employe = user

                    if not user.is_superuser:
                        try:
                            location.agence = user.profil.agence
                        except AttributeError:
                            pass

                    duree = (location.retour_prevue - location.date_debut).days
                    if duree <= 0:
                        messages.error(
                            request,
                            "La date de retour prévue doit être postérieure à la date de début.",
                        )
                        return render(
                            request,
                            "core/pages/location_form.html",
                            {
                                "form": form,
                                "equipements": equipements_qs,
                                "client_agence_map": client_agence_map,
                            },
                        )

                    montant_total = 0.00
                    for eq_id in equipements_ids:
                        equipement = Equipement.objects.get(pk=eq_id)
                        prix_jour = float(getattr(equipement, "prix_journalier", 0.00))
                        montant_total += prix_jour * duree

                    location.montant_total = montant_total
                    location.caution = round(montant_total * 0.50, 2)
                    location.save()

                    for eq_id in equipements_ids:
                        equipement = Equipement.objects.get(pk=eq_id)
                        prix_jour = float(getattr(equipement, "prix_journalier", 0.00))
                        LocationEquipement.objects.create(
                            location=location,
                            equipement=equipement,
                            prix_journalier_applique=prix_jour,
                        )

                        # 2. Mettre à jour le statut de l'équipement à "loué"
                        # (Adapte la valeur 'loue' ou 'loué' selon ce qui est défini dans ton modèle Equipement)
                        equipement.statut = "loue"
                        equipement.save()

                    messages.success(
                        request, f"La location #{location.id} a été créée avec succès."
                    )
                    return redirect("core:liste_locations")

            except Exception as e:
                messages.error(
                    request, f"Erreur lors de la création de la location : {e}"
                )
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
            "equipements": equipements_qs,
            "client_agence_map": client_agence_map,
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
            # 👈 Correction : on utilise 'profil' comme dans le dashboard
            agence_employe = user.profil.agence
            locations = Location.objects.filter(agence=agence_employe)
        except AttributeError:
            locations = Location.objects.none()

    locations = locations.select_related(
        "client", "agence", "employe"
    ).prefetch_related("lignes_location__equipement")

    return render(request, "core/pages/liste_locations.html", {"locations": locations})


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

    return render(request, "core/pages/location_detail.html", {"location": location})


@login_required
@never_cache
@login_required
@never_cache
def modifier_location(request, pk):
    location = get_object_or_404(Location, pk=pk)
    user = request.user

    if not user.is_superuser:
        try:
            if location.agence != user.profil.agence:
                return redirect("core:liste_locations")
        except AttributeError:
            return redirect("core:liste_locations")

    client_agence_map = dict(Client.objects.values_list("id", "agence_id"))

    if request.method == "POST":
        form = LocationForm(request.POST, instance=location, user=user)
        equipements_ids = request.POST.getlist("equipements")

        if form.is_valid() and equipements_ids:
            try:
                with transaction.atomic():
                    # 1. Libérer les anciens équipements
                    ancienne_lignes = location.lignes_location.all()
                    anciens_equipements_ids = [ligne.equipement_id for ligne in ancienne_lignes]
                    Equipement.objects.filter(id__in=anciens_equipements_ids).update(statut='disponible')
                    ancienne_lignes.delete()

                    # 2. Sauvegarder les modifications du formulaire
                    loc_modifiee = form.save(commit=False)
                    
                    duree = (loc_modifiee.retour_prevue - loc_modifiee.date_debut).days
                    if duree <= 0:
                        messages.error(request, "La date de retour prévue doit être postérieure à la date de début.")
                        return redirect("core:modifier_location", pk=pk)

                    montant_total = 0.00
                    for eq_id in equipements_ids:
                        equipement = Equipement.objects.get(pk=eq_id)
                        prix_jour = float(getattr(equipement, "prix_journalier", 0.00))
                        montant_total += prix_jour * duree

                    loc_modifiee.montant_total = montant_total
                    loc_modifiee.caution = round(montant_total * 0.50, 2)
                    loc_modifiee.save()

                    # 3. Créer les nouvelles lignes et passer les équipements en 'loue'
                    for eq_id in equipements_ids:
                        equipement = Equipement.objects.get(pk=eq_id)
                        prix_jour = float(getattr(equipement, "prix_journalier", 0.00))
                        
                        LocationEquipement.objects.create(
                            location=loc_modifiee,
                            equipement=equipement,
                            prix_journalier_applique=prix_jour,
                        )
                        equipement.statut = 'loue'
                        equipement.save()

                    messages.success(request, f"La location #{location.id} a été modifiée avec succès.")
                    return redirect("core:liste_locations")

            except Exception as e:
                messages.error(request, f"Erreur lors de la modification : {e}")
        else:
            if not equipements_ids:
                messages.error(request, "Veuillez sélectionner au moins un équipement.")
    else:
        form = LocationForm(instance=location, user=user)

    # Récupérer les équipements disponibles (en excluant les autres locations en cours, mais en gardant ceux de CETte location)
    equipements_actuels_ids = list(location.lignes_location.values_list('equipement_id', flat=True))
    equipements_autres_loues = LocationEquipement.objects.filter(location__retour_reelle__isnull=True).exclude(location=location).values_list('equipement_id', flat=True)

    if user.is_superuser:
        equipements = Equipement.objects.exclude(id__in=equipements_autres_loues)
    else:
        try:
            equipements = Equipement.objects.filter(agence=user.profil.agence).exclude(id__in=equipements_autres_loues)
        except AttributeError:
            equipements = Equipement.objects.none()

    return render(
        request,
        "core/pages/location_form.html",
        {
            "form": form,
            "equipements": equipements,
            "client_agence_map": client_agence_map,
            "location": location,
            "equipements_actuels_ids": equipements_actuels_ids, # 👈 On transmet les IDs actuels au template
            "action": "Modifier",
        },
    )

@login_required
@never_cache
def supprimer_location(request, pk):
    """
    Supprime une location et remet automatiquement les équipements associés au statut 'disponible'.
    """
    location = get_object_or_404(Location, pk=pk)
    user = request.user

    # Sécurité agence
    if not user.is_superuser:
        try:
            if location.agence != user.profil.agence:
                return redirect("core:liste_locations")
        except AttributeError:
            return redirect("core:liste_locations")

    if request.method == "POST":
        with transaction.atomic():
            # Remettre les équipements liés au statut 'disponible' avant de supprimer
            equipements_ids = location.lignes_location.values_list(
                "equipement_id", flat=True
            )
            Equipement.objects.filter(id__in=equipements_ids).update(
                statut="disponible"
            )

            location.delete()
            messages.success(
                request,
                "La location a été supprimée avec succès et les équipements ont été libérés.",
            )
        return redirect("core:liste_locations")

    return redirect("core:liste_locations")
