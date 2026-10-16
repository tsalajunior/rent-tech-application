from django.shortcuts import render
from .models import Equipement, Client, Location, Agence


def dashboard(views_request):
    """
    Vue du tableau de bord de l'employé au comptoir.
    """
    total_clients = Client.objects.count()
    total_equipements = Equipement.objects.count()
    locations_en_cours = Location.objects.filter(retour_reelle__isnull=True).count()

    context = {
        "total_clients": total_clients,
        "total_equipements": total_equipements,
        "locations_en_cours": locations_en_cours,
    }
    return render(views_request, "core/pages/dashboard.html", context)


def liste_equipements(views_request):
    """
    Vue listant tous les équipements disponibles dans les agences.
    """
    equipements = Equipement.objects.all()
    context = {
        "equipements": equipements,
    }
    return render(views_request, "core/pages/liste_equipements.html", context)


def liste_clients(views_request):
    """
    Vue listant les clients enregistrés.
    """
    clients = Client.objects.all()
    context = {
        "clients": clients,
    }
    return render(views_request, "core/pages/liste_clients.html", context)


