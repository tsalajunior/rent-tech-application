from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Agence, Categorie, Equipement, Client, Location, LocationEquipement, ProfilEmploye


@admin.register(Agence)
class AgenceAdmin(admin.ModelAdmin):
    list_display = ("nom", "ville", "adresse")
    search_fields = ("nom", "ville")


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ("nom","description")
    search_fields = ("nom","description")


@admin.register(Equipement)
class EquipementAdmin(admin.ModelAdmin):
    list_display = ("reference", "nom", "prix_journalier", "categorie", "agence", "statut")
    list_filter = ("categorie", "agence", "statut")
    search_fields = ("reference", "nom")


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("nom", "prenom", "email", "telephone")
    search_fields = ("nom", "prenom", "email", "telephone")


# class LocationEquipementInline(admin.TabularInline):
#     model = LocationEquipement
#     extra = 1


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "client",
        "agence",
        "employe",
        "date_debut",
        "retour_prevue",
        "montant_total",
        "caution",
        "date_creation",
    )
    list_filter = ("agence", "date_debut", "date_creation")
    search_fields = ("client__nom", "client__prenom", "client__email", 'employe__username')
    # inlines = [LocationEquipementInline]


@admin.register(LocationEquipement)
class LocationEquipementAdmin(admin.ModelAdmin):
    list_display = ("location", "equipement", "prix_journalier_applique")
    list_filter = ("equipement", "location__agence")
    search_fields = ("equipement__nom", "equipement__reference")


# --- Gestion des Profils Employés liés aux Agences ---

class ProfilEmployeInline(admin.StackedInline):
    """
    Permet d'afficher et de modifier l'agence de l'employé directement
    depuis la page de modification d'un utilisateur dans l'admin Django.
    """
    model = ProfilEmploye
    can_delete = False
    verbose_name_plural = 'Profil Agence'

# On décoche l'UserAdmin par défaut de Django pour y inclure notre inline d'agence
class CustomUserAdmin(UserAdmin):
    inlines = (ProfilEmployeInline,)


# On désenregistre l'User par défaut pour réenregistrer notre version enrichie
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)