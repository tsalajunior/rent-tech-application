from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Equipement, Client, Location
from django.views.decorators.cache import never_cache
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from .forms import EquipementForm


@login_required
@never_cache
def dashboard(request):
    """
    Tableau de bord dynamique :
    - Vue globale pour l'administrateur principal.
    - Vue filtrée par agence pour l'employé simple.
    """
    user = request.user

    if user.is_superuser:
        # Vue globale SuperAdmin
        total_clients = Client.objects.count()
        total_equipements = Equipement.objects.count()
        locations_en_cours = Location.objects.filter(retour_reelle__isnull=True).count()
        agence_libelle = "Administration Centrale (Toutes les Agences)"
    else:
        # Vue restreinte à l'agence de l'employé
        try:
            employe_agence = user.profil.agence
        except AttributeError:
            employe_agence = None

        if employe_agence:
            # Filtrage strict par agence
            total_equipements = Equipement.objects.filter(agence=employe_agence).count()
            locations_en_cours = Location.objects.filter(
                agence=employe_agence, retour_reelle__isnull=True
            ).count()
            # Clients ayant effectué une location dans cette agence
            total_clients = (
                Client.objects.filter(locations__agence=employe_agence)
                .distinct()
                .count()
            )
            agence_libelle = f"Agence de {employe_agence.ville} ({employe_agence.nom})"
        else:
            total_equipements = 0
            locations_en_cours = 0
            total_clients = 0
            agence_libelle = "Aucune agence assignée"

    context = {
        "total_clients": total_clients,
        "total_equipements": total_equipements,
        "locations_en_cours": locations_en_cours,
        "agence_libelle": agence_libelle,
    }
    return render(request, "core/pages/dashboard.html", context)


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
def liste_clients(request):
    """
    Liste des clients filtrée par agence pour les employés.
    """
    user = request.user
    if user.is_superuser:
        clients = Client.objects.all()
    else:
        try:
            employe_agence = user.profil.agence
            clients = Client.objects.filter(locations__agence=employe_agence).distinct()
        except AttributeError:
            clients = Client.objects.none()

    return render(request, "core/pages/liste_clients.html", {"clients": clients})


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
