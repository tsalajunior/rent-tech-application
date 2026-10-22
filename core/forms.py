from django import forms
from .models import Equipement


class EquipementForm(forms.ModelForm):
    class Meta:
        model = Equipement
        fields = [
            "reference",
            "nom",
            "categorie",
            "agence",
            "prix_journalier",
            "statut",
        ]
        widgets = {
            "reference": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-renttech-primary focus:outline-none text-sm"
                }
            ),
            "nom": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-renttech-primary focus:outline-none text-sm"
                }
            ),
            "categorie": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-renttech-primary focus:outline-none text-sm"
                }
            ),
            "agence": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-renttech-primary focus:outline-none text-sm"
                }
            ),
            "prix_journalier": forms.NumberInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-renttech-primary focus:outline-none text-sm"
                }
            ),
            "statut": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-renttech-primary focus:outline-none text-sm"
                }
            ),
        }
