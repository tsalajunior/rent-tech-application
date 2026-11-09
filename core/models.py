from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP


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

    STATUT_CHOICES = [
        ("en_cours", "En cours"),
        ("etendue", "Étendue"),
        ("terminee", "Terminée"),
        ("retard", "En retard"),
        ("annulee", "Annulée"),
    ]

    client = models.ForeignKey(
        Client, on_delete=models.PROTECT, related_name="locations"
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

    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_cours')

    @property
    def est_annulable(self):
        """Une location active peut être annulée jusqu'à 24 heures après sa création."""
        if not self.est_active or not self.date_creation:
            return False
        age = timezone.now() - self.date_creation
        return timedelta(0) <= age <= timedelta(hours=24)

    @property
    def montant_loyer_a_rembourser(self):
        if self.statut != "annulee":
            return Decimal("0.00")
        return (self.montant_total * Decimal("0.90")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    @property
    def montant_caution_a_rembourser(self):
        if self.statut == "annulee":
            return self.caution
        if self.retour_reelle or self.statut == "terminee":
            penalite = Decimal(str(self.penalite_retard or 0))
            return max(self.caution - penalite, Decimal("0.00"))
        return Decimal("0.00")

    @property
    def montant_total_a_rembourser(self):
        return self.montant_loyer_a_rembourser + self.montant_caution_a_rembourser

    @property
    def montant_loyer_conserve(self):
        if self.statut != "annulee":
            return Decimal("0.00")
        return (self.montant_total * Decimal("0.10")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    @property
    def statut_affiche(self):
        if self.statut == "annulee":
            return "annulee"
        if self.retour_reelle or self.statut == "terminee":
            return "terminee"
        if self.retour_prevue < timezone.localdate():
            return "retard"
        if self.statut == "etendue":
            return "etendue"
        return "en_cours"

    @property
    def est_active(self):
        return not self.retour_reelle and self.statut not in ("terminee", "annulee")

    date_debut = models.DateField()
    retour_prevue = models.DateField()
    retour_reelle = models.DateField(null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    caution = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    montant_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    penalite_retard = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00
    )

    def calculer_penalite_retard(self, date_fin):
        jours_retard = max(0, (date_fin - self.retour_prevue).days)
        return (
            self.montant_total * Decimal("0.10") * jours_retard
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

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


class ProlongationLocation(models.Model):
    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name="prolongations"
    )
    ancienne_date = models.DateField()
    nouvelle_date = models.DateField()
    montant_supplementaire = models.DecimalField(max_digits=10, decimal_places=2)
    employe = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prolongations_enregistrees",
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Prolongation de la location #{self.location_id}"


class Notification(models.Model):
    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications"
    )
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications_effectuees",
    )
    agence = models.ForeignKey(
        Agence,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    event_type = models.CharField(max_length=40)
    title = models.CharField(max_length=180)
    message = models.TextField()
    target_url = models.CharField(max_length=255, blank=True)
    event_key = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        constraints = [
            models.UniqueConstraint(
                fields=("recipient", "event_key"),
                name="unique_notification_per_recipient_event",
            )
        ]

    def __str__(self):
        return f"{self.title} — {self.recipient.username}"


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
