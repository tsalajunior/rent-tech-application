from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("equipements/", views.liste_equipements, name="liste_equipements"),
    path('equipements/ajouter/', views.equipement_ajouter, name='equipement_ajouter'),
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
]
