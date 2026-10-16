from django.contrib import admin
from .models import Agence, Categorie, Equipement, Client, Location, LocationEquipement


@admin.register(Agence)
class AgenceAdmin(admin.ModelAdmin):
    list_display = ("nom", "ville", "adresse")
    search_fields = ("nom", "ville")


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ("nom",)
    search_fields = ("nom",)


@admin.register(Equipement)
class EquipementAdmin(admin.ModelAdmin):
    list_display = ("reference", "nom", "prix_journalier", "categorie", "agence")
    list_filter = ("categorie", "agence")
    search_fields = ("reference", "nom")


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("nom", "prenom", "email", "telephone")
    search_fields = ("nom", "prenom", "email", "telephone")


class LocationEquipementInline(admin.TabularInline):
    model = LocationEquipement
    extra = 1


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
    search_fields = ("client__nom", "client__prenom", "client__email")
    inlines = [LocationEquipementInline]


@admin.register(LocationEquipement)
class LocationEquipementAdmin(admin.ModelAdmin):
    list_display = ("location", "equipement", "prix_journalier_applique")
    list_filter = ('equipement', 'location__agence')
    search_fields = ('equipement__nom', 'equipement__reference')


