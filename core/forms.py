from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from datetime import date

from django.utils import timezone
from .models import Agence, Equipement, Client, ProfilEmploye, Categorie, Location


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


class AgenceForm(forms.ModelForm):
    class Meta:
        model = Agence
        fields = ["nom", "ville", "adresse"]
        widgets = {
            "nom": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-renttech-primary"
                }
            ),
            "ville": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-renttech-primary"
                }
            ),
            "adresse": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-renttech-primary",
                }
            ),
        }


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ["client", "agence", "date_debut", "retour_prevue", "caution"]
        widgets = {
            "client": forms.Select(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-renttech-primary"
                }
            ),
            "agence": forms.Select(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-renttech-primary"
                }
            ),
            "date_debut": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "type": "date",
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-renttech-primary",
                },
            ),
            "retour_prevue": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "type": "date",
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-renttech-primary",
                },
            ),
            "caution": forms.NumberInput(
                attrs={
                    "readonly": "readonly",
                    "class": "w-full px-3 py-2 border border-gray-300 bg-gray-100 text-gray-700 rounded-md focus:outline-none cursor-not-allowed",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # 1. Empêcher de sélectionner une date antérieure à aujourd'hui directement dans le calendrier HTML5
        today_str = date.today().isoformat()
        self.fields["date_debut"].widget.attrs["min"] = today_str
        self.fields["retour_prevue"].widget.attrs["min"] = today_str

        # Si l'utilisateur n'est pas superuser, on restreint l'agence à la sienne
        if user and not user.is_superuser:
            try:
                self.fields["agence"].queryset = Agence.objects.filter(
                    id=user.profil.agence.id
                )
                self.fields["agence"].initial = user.profil.agence
                # Restreindre aussi les clients à l'agence de l'employé
                self.fields["client"].queryset = Client.objects.filter(
                    agence=user.profil.agence
                )
            except AttributeError:
                pass

        # Si le formulaire est déjà lié à une instance ou à des données POST contenant une agence,
        # on peut affiner le queryset des clients pour ne garder que ceux de cette agence.
        if self.data and "agence" in self.data:
            try:
                agence_id = int(self.data.get("agence"))
                self.fields["client"].queryset = Client.objects.filter(
                    agence_id=agence_id
                )
            except (ValueError, TypeError):
                pass
        elif self.instance and self.instance.pk and self.instance.agence:
            self.fields["client"].queryset = Client.objects.filter(
                agence=self.instance.agence
            )

    # 3. Validation de sécurité côté serveur (Empêche le contournement)
    def clean_date_debut(self):
        date_debut = self.cleaned_data.get("date_debut")
        if date_debut and date_debut < date.today():
            raise ValidationError(
                "La date de début de location ne peut pas être antérieure à aujourd'hui."
            )
        return date_debut

    def clean(self):
        cleaned_data = super().clean()
        date_debut = cleaned_data.get("date_debut")
        retour_prevue = cleaned_data.get("retour_prevue")

        # La règle de la date passée s'applique UNIQUEMENT à la création (pas en modification)
        if not self.instance.pk and date_debut and date_debut < timezone.now().date():
            self.add_error(
                "date_debut", "La date de début ne peut pas être dans le passé."
            )

        if date_debut and retour_prevue and retour_prevue <= date_debut:
            self.add_error(
                "retour_prevue",
                "La date de retour prévue doit être postérieure à la date de début.",
            )

        return cleaned_data
