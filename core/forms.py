from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from datetime import date
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
        fields = ['client', 'agence', 'date_debut', 'retour_prevue', 'caution']
        widgets = {
            'client': forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-renttech-primary'}),
            'agence': forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-renttech-primary'}),
            'date_debut': forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-renttech-primary'}),
            'retour_prevue': forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-renttech-primary'}),
            'caution': forms.NumberInput(attrs={'readonly': 'readonly', 'class': 'w-full px-3 py-2 border border-gray-300 bg-gray-100 text-gray-700 rounded-md focus:outline-none cursor-not-allowed'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # 1. Empêcher de sélectionner une date antérieure à aujourd'hui directement dans le calendrier HTML5
        today_str = date.today().isoformat()
        self.fields['date_debut'].widget.attrs['min'] = today_str
        self.fields['retour_prevue'].widget.attrs['min'] = today_str

        # 2. Gestion des droits agence et clients (comme vu précédemment)
        if user and not user.is_superuser:
            try:
                agence_employe = user.profil.agence
                self.fields['agence'].queryset = Agence.objects.filter(id=agence_employe.id)
                self.initial['agence'] = agence_employe
                self.fields['client'].queryset = Client.objects.filter(agence=agence_employe)
            except AttributeError:
                self.fields['agence'].queryset = Agence.objects.none()
                self.fields['client'].queryset = Client.objects.none()
        else:
            self.fields['agence'].queryset = Agence.objects.all()
            self.fields['client'].queryset = Client.objects.all()

    # 3. Validation de sécurité côté serveur (Empêche le contournement)
    def clean_date_debut(self):
        date_debut = self.cleaned_data.get('date_debut')
        if date_debut and date_debut < date.today():
            raise ValidationError("La date de début de location ne peut pas être antérieure à aujourd'hui.")
        return date_debut

    def clean(self):
        cleaned_data = super().clean()
        date_debut = cleaned_data.get('date_debut')
        retour_prevue = cleaned_data.get('retour_prevue')

        if date_debut and retour_prevue and retour_prevue <= date_debut:
            self.add_error('retour_prevue', "La date de retour prévue doit être strictement postérieure à la date de début.")
        
        return cleaned_data
