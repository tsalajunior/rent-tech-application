from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView

app_name = "core"

urlpatterns = [
    path("logout/", LogoutView.as_view(next_page="core:login"), name="logout"),
    path("", views.dashboard, name="dashboard"),
    path("equipements/", views.liste_equipements, name="liste_equipements"),
    path("equipements/ajouter/", views.equipement_ajouter, name="equipement_ajouter"),
    path(
        "equipements/<int:pk>/supprimer/",
        views.equipement_supprimer,
        name="equipement_supprimer",
    ),
    path(
        "equipements/<int:pk>/modifier/",
        views.equipement_modifier,
        name="equipement_modifier",
    ),
    path("clients/", views.liste_clients, name="liste_clients"),
    path("clients/ajouter/", views.client_ajouter, name="client_ajouter"),
    path("clients/<int:pk>/modifier/", views.client_modifier, name="client_modifier"),
    path(
        "clients/<int:pk>/supprimer/", views.client_supprimer, name="client_supprimer"
    ),
    path("utilisateurs/", views.liste_utilisateurs, name="liste_utilisateurs"),
    path(
        "utilisateurs/<int:pk>/modifier/",
        views.utilisateur_modifier,
        name="utilisateur_modifier",
    ),
    path(
        "utilisateurs/<int:pk>/toggle-status/",
        views.utilisateur_toggle_status,
        name="utilisateur_toggle_status",
    ),
    path("mon-profil/", views.mon_profil, name="mon_profil"),
    path("categories/", views.liste_categories, name="liste_categories"),
    path("categories/ajouter/", views.categorie_ajouter, name="categorie_ajouter"),
    path(
        "categories/<int:pk>/modifier/",
        views.categorie_modifier,
        name="categorie_modifier",
    ),
    path(
        "categories/<int:pk>/supprimer/",
        views.categorie_supprimer,
        name="categorie_supprimer",
    ),
    path("agences/", views.liste_agences, name="liste_agences"),
    path("agences/ajouter/", views.agence_ajouter, name="agence_ajouter"),
    path("agences/<int:pk>/modifier/", views.agence_modifier, name="agence_modifier"),
    path(
        "agences/<int:pk>/supprimer/", views.agence_supprimer, name="agence_supprimer"
    ),
    path("locations/", views.liste_locations, name="liste_locations"),
    path("liste_locations/", views.liste_locations),
    path("locations/ajouter/", views.creer_location, name="creer_location"),
    path("locations/<int:pk>/", views.detail_location, name="detail_location"),
    path(
        "locations/<int:pk>/modifier/",
        views.modifier_location,
        name="modifier_location",
    ),
    path(
        "locations/<int:pk>/supprimer/",
        views.supprimer_location,
        name="supprimer_location",
    ),
]
