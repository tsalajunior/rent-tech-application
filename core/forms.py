from django import forms
from django.contrib.auth.models import User
from .models import Agence, Equipement, Client, ProfilEmploye, Categorie


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


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ["nom", "prenom", "email", "telephone", "agence"]
        widgets = {
            "nom": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-renttech-primary focus:outline-none text-sm"
                }
            ),
            "prenom": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-renttech-primary focus:outline-none text-sm"
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-renttech-primary focus:outline-none text-sm"
                }
            ),
            "telephone": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-renttech-primary focus:outline-none text-sm"
                }
            ),
            "agence": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-renttech-primary focus:outline-none text-sm"
                }
            ),
        }


class AdminUserForm(forms.ModelForm):
    agence = forms.ModelChoiceField(
        queryset=Agence.objects.all(),
        widget=forms.Select(
            attrs={
                "class": "w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-renttech-primary focus:outline-none text-sm"
            }
        ),
        label="Agence",
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "is_active"]
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-renttech-primary focus:outline-none text-sm"
                }
            ),
            "first_name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-renttech-primary focus:outline-none text-sm"
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-renttech-primary focus:outline-none text-sm"
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-renttech-primary focus:outline-none text-sm"
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-renttech-primary focus:ring-renttech-primary border-gray-300 rounded"
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pré-remplir l'agence si l'utilisateur a un profil associé
        if self.instance and self.instance.pk:
            try:
                self.fields["agence"].initial = self.instance.profil.agence
            except ProfilEmploye.DoesNotExist:
                pass

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            agence = self.cleaned_data.get("agence")
            profil, created = ProfilEmploye.objects.get_or_create(user=user)
            profil.agence = agence
            profil.save()
        return user


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email"]
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-renttech-primary focus:outline-none text-sm"
                }
            ),
            "first_name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-renttech-primary focus:outline-none text-sm"
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-renttech-primary focus:outline-none text-sm"
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-renttech-primary focus:outline-none text-sm"
                }
            ),
        }


class CategorieForm(forms.ModelForm):
    class Meta:
        model = Categorie
        fields = ["nom", "description"]
        widgets = {
            "nom": forms.TextInput(
                attrs={
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-renttech-primary focus:outline-none text-sm"
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-renttech-primary focus:outline-none text-sm",
                }
            ),
        }


