from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
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

        # Preserve existing past dates when editing while blocking new past dates.
        today = timezone.localdate()
        date_debut_min = (
            self.instance.date_debut.isoformat()
            if self.instance.pk
            else today.isoformat()
        )
        retour_prevue_min = (
            min(today, self.instance.retour_prevue).isoformat()
            if self.instance.pk
            else today.isoformat()
        )
        self.fields["date_debut"].widget.attrs["min"] = date_debut_min
        self.fields["retour_prevue"].widget.attrs["min"] = retour_prevue_min

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
        if date_debut and date_debut < timezone.localdate() and (
            not self.instance.pk or date_debut != self.instance.date_debut
        ):
            raise ValidationError(
                "La date de début de location ne peut pas être antérieure à aujourd'hui."
            )
        return date_debut

    def clean(self):
        cleaned_data = super().clean()
        agence = cleaned_data.get("agence")
        client = cleaned_data.get("client")
        date_debut = cleaned_data.get("date_debut")
        retour_prevue = cleaned_data.get("retour_prevue")

        if agence and client and client.agence_id != agence.id:
            self.add_error("client", "Le client doit appartenir à l'agence choisie.")

        if date_debut and retour_prevue and retour_prevue <= date_debut:
            self.add_error(
                "retour_prevue",
                "La date de retour prévue doit être postérieure à la date de début.",
            )

        return cleaned_data


class ProlongationLocationForm(forms.Form):
    nouvelle_date = forms.DateField(
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-renttech-primary",
            }
        ),
    )
