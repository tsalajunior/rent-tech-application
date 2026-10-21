from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Equipement, Client, Location
from django.views.decorators.cache import never_cache
from django.core.paginator import Paginator
from django.db.models import Q


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
    """
    Catalogue des équipements filtré par agence pour les employés.
    """
    user = request.user
    query = request.GET.get("q", "")

    # 1. Filtrage initial selon le cloisonnement agence / superuser
    if user.is_superuser:
        equipements = Equipement.objects.all()
    else:
        try:
            employe_agence = user.profil.agence
            equipements = Equipement.objects.filter(agence=employe_agence)
        except AttributeError:
            equipements = Equipement.objects.none()

    # 2. Filtrage dynamique par la barre de recherche (Référence, Nom ou Catégorie)
    if query:
        equipements = equipements.filter(
            Q(reference__icontains=query)
            | Q(nom__icontains=query)
            | Q(categorie__nom__icontains=query)
        )

    # Tri par ordre décroissant (les plus récents en premier)
    equipements = equipements.order_by("-id")

    # 3. Pagination : 10 éléments par page
    paginator = Paginator(equipements, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "equipements": page_obj,  # On transmet l'objet de pagination au template
        "query": query,
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
