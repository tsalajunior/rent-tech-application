from django.db import models
from django.contrib.auth.models import User


class Agence(models.Model):
    """
    Modèle représentant une agence.
    """

    nom = models.CharField(max_length=100)
    ville = models.CharField(max_length=100)
    adresse = models.TextField(max_length=250)

    def __str__(self):
        return f"{self.nom} ({self.ville})"

    def a_des_dependances(self):
        """Vérifie dynamiquement et exhaustivement si l'agence est liée à la moindre donnée (clients, équipements, locations, utilisateurs, etc.)"""
        for rel in self._meta.related_objects:
            accessor_name = rel.get_accessor_name()
            manager = getattr(self, accessor_name, None)
            if manager and manager.exists():
                return True
        return False


class Categorie(models.Model):
    """
    Modèle représentant une catégorie.
    """

    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nom


class Equipement(models.Model):
    """
    Modèle représentant un équipement.
    """

    # Choix de statuts pour un équipement de location
    STATUT_CHOICES = [
        ("disponible", "Disponible"),
        ("loue", "Loué"),
        ("maintenance", "En maintenance"),
    ]

    reference = models.CharField(max_length=50, unique=True)
    nom = models.CharField(max_length=150)
    prix_journalier = models.DecimalField(
        max_digits=10, decimal_places=2
    )  # Coût de location par jour
    statut = models.CharField(
        max_length=20, choices=STATUT_CHOICES, default="disponible"
    )
    categorie = models.ForeignKey(
        Categorie, on_delete=models.CASCADE, related_name="equipements"
    )
    agence = models.ForeignKey(
        Agence, on_delete=models.CASCADE, related_name="equipements"
    )

    def __str__(self):
        return f"{self.nom} [{self.reference} {self.categorie.nom}]"


class Client(models.Model):
    """
    Modèle représentant un client.
    """

    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(unique=True)
    telephone = models.CharField(max_length=20)
    agence = models.ForeignKey(Agence, on_delete=models.CASCADE, related_name="clients")

    class Meta:
        # Optionnel : Empêche d'avoir deux fois le même email dans la même agence
        unique_together = ("email", "agence")

    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.agence.nom})"


class Location(models.Model):
    """
    Modèle représentant une location.
    """

    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name="locations"
    )
    agence = models.ForeignKey(
        Agence, on_delete=models.CASCADE, related_name="locations"
    )
    employe = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="locations_enregistrees",
    )

    date_debut = models.DateField()
    retour_prevue = models.DateField()
    retour_reelle = models.DateField(null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    caution = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    montant_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"Location #{self.id} - Client: {self.client}"


class LocationEquipement(models.Model):
    """
    Modèle représentant la relation entre une location et un équipement.
    """

    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name="lignes_location"
    )
    equipement = models.ForeignKey(
        Equipement, on_delete=models.CASCADE, related_name="lignes_location"
    )
    prix_journalier_applique = models.DecimalField(
        max_digits=10, decimal_places=2
    )  # Sécurise l'historique en cas de changement de tarif

    def __str__(self):
        return f"Location {self.location.id} -> Équipement {self.equipement.nom}"


class ProfilEmploye(models.Model):
    """
    Modèle représentant le profil d'un employé.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profil")
    agence = models.ForeignKey(
        "Agence",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employes",
    )

    def __str__(self):
        return f"{self.user.username} - Agence: {self.agence.nom if self.agence else 'Aucune'}"
