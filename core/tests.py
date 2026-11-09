import csv
from io import StringIO

from django.core.management import call_command
from django.template.loader import get_template
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import resolve, reverse
from types import SimpleNamespace
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.utils import timezone
from reportlab.platypus import Paragraph as ReportLabParagraph

from .forms import LocationForm, ProlongationLocationForm
from .models import (
    Agence,
    Categorie,
    Client,
    Equipement,
    Location,
    LocationEquipement,
    Notification,
    ProlongationLocation,
    ProfilEmploye,
)
from .views import (
    _arrondir_montant,
    _prix_location,
    liste_clients,
    liste_locations,
    retourner_location,
    telecharger_location_pdf,
)


class LocationUrlTests(SimpleTestCase):
    def test_legacy_location_list_url_resolves(self):
        match = resolve("/liste_locations/")

        self.assertEqual(match.func, liste_locations)

    def test_named_location_list_url_remains_canonical(self):
        self.assertEqual(reverse("core:liste_locations"), "/locations/")

    def test_clients_list_url_resolves(self):
        self.assertEqual(resolve("/clients/").func, liste_clients)

    def test_location_pdf_url_resolves(self):
        self.assertEqual(
            resolve("/locations/12/pdf/").func, telecharger_location_pdf
        )

    def test_location_extension_url_resolves(self):
        self.assertEqual(
            resolve("/locations/12/prolonger/").url_name, "etendre_location"
        )


class LocationTemplateTests(SimpleTestCase):
    def test_location_templates_are_loadable(self):
        get_template("core/pages/liste_locations.html")
        get_template("core/pages/location_form.html")

    def test_location_detail_renders_pdf_button(self):
        html = get_template("core/pages/location_detail.html").render(
            {
                "location": SimpleNamespace(
                    id=12,
                    agence=SimpleNamespace(nom="Agence de test"),
                    employe=SimpleNamespace(username="employe"),
                    client=SimpleNamespace(
                        nom="Martin",
                        prenom="Alice",
                        email="alice@example.test",
                        telephone="0123456789",
                    ),
                    date_debut=date(2026, 11, 1),
                    retour_prevue=date(2026, 11, 5),
                    retour_reelle=date(2026, 11, 7),
                    statut="terminee",
                    lignes_location=SimpleNamespace(all=lambda: []),
                    montant_total=Decimal("100.00"),
                    penalite_retard=Decimal("10.00"),
                    caution=Decimal("50.00"),
                    montant_loyer_a_rembourser=Decimal("0.00"),
                    montant_caution_a_rembourser=Decimal("50.00"),
                    montant_loyer_conserve=Decimal("0.00"),
                ),
                "prolongation_form": ProlongationLocationForm(),
                "renttech_name": "RentTech",
                "renttech_description": (
                    "Système de location de matériels informatiques et électroniques."
                ),
            }
        )

        self.assertIn("RentTech_Logo.jpg", html)
        self.assertIn("RentTech", html)
        self.assertIn(
            "Système de location de matériels informatiques et électroniques.",
            html,
        )
        self.assertIn("Générer le PDF", html)
        self.assertIn(reverse("core:telecharger_location_pdf", args=[12]), html)
        self.assertIn("Retour réel :</span> 07/11/2026", html)

    def test_location_form_renders_client_agency_map_as_json(self):
        html = get_template("core/pages/location_form.html").render(
            {"client_agence_map": {1: 2}}
        )

        self.assertIn(
            '<script id="client-agence-map" type="application/json">{"1": 2}</script>',
            html,
        )
        self.assertNotIn("{% for c in clients %}", html)

    def test_dashboard_renders_included_templates(self):
        html = get_template("core/pages/dashboard.html").render(
            {
                "user": SimpleNamespace(username="test", is_superuser=False),
                "agence_libelle": "Agence de test",
                "total_clients": 1,
                "total_equipements": 2,
                "locations_en_cours": 3,
            }
        )

        self.assertIn("Total clients", html)
        self.assertIn("Voir les équipements", html)
        self.assertNotIn("{% include", html)


class LocationPdfTests(SimpleTestCase):
    def creer_location_pdf(self, statut, retour_reelle):
        return SimpleNamespace(
            id=12,
            statut=statut,
            agence=SimpleNamespace(nom="Agence de test"),
            employe=SimpleNamespace(username="employe"),
            client=SimpleNamespace(
                nom="Martin",
                prenom="Alice",
                email="alice@example.test",
                telephone="0123456789",
            ),
            date_debut=date(2026, 11, 1),
            retour_prevue=date(2026, 11, 5),
            retour_reelle=retour_reelle,
            lignes_location=SimpleNamespace(
                all=lambda: [
                    SimpleNamespace(
                        equipement=SimpleNamespace(
                            nom="Perceuse", reference="REF-1"
                        ),
                        prix_journalier_applique=Decimal("25.00"),
                    )
                ]
            ),
            montant_total=Decimal("100.00"),
            penalite_retard=Decimal("10.00"),
            caution=Decimal("50.00"),
            montant_loyer_a_rembourser=(
                Decimal("90.00") if statut == "annulee" else Decimal("0.00")
            ),
            montant_loyer_conserve=(
                Decimal("10.00") if statut == "annulee" else Decimal("0.00")
            ),
            montant_caution_a_rembourser=(
                Decimal("50.00") if statut == "annulee" else Decimal("40.00")
            ),
            montant_total_a_rembourser=(
                Decimal("140.00") if statut == "annulee" else Decimal("40.00")
            ),
        )

    def test_pdf_download_returns_a_pdf_attachment(self):
        location = self.creer_location_pdf("terminee", date(2026, 11, 7))
        request = RequestFactory().get("/locations/12/pdf/")
        request.user = SimpleNamespace(is_superuser=True)

        with (
            patch("core.views.get_object_or_404", return_value=location),
            patch("core.views.Paragraph", wraps=ReportLabParagraph) as paragraph,
        ):
            response = telecharger_location_pdf.__wrapped__(request, 12)

        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(
            response["Content-Disposition"],
            'attachment; filename="location-12.pdf"',
        )
        self.assertTrue(response.content.startswith(b"%PDF-"))
        self.assertIn(b"/Subtype /Image", response.content)
        self.assertTrue(
            any(
                "Retour réel : 07/11/2026" in call.args[0]
                for call in paragraph.call_args_list
            )
        )
        self.assertTrue(
            any(
                "Clôture — remboursement à effectuer" in call.args[0]
                and "Caution restante après imputation des pénalités : 40.00 €"
                in call.args[0]
                and "Total à rembourser au client : 40.00 €" in call.args[0]
                for call in paragraph.call_args_list
            )
        )

    def test_cancelled_rental_pdf_includes_refund_breakdown(self):
        location = self.creer_location_pdf("annulee", None)
        request = RequestFactory().get("/locations/12/pdf/")
        request.user = SimpleNamespace(is_superuser=True)

        with (
            patch("core.views.get_object_or_404", return_value=location),
            patch("core.views.Paragraph", wraps=ReportLabParagraph) as paragraph,
        ):
            response = telecharger_location_pdf.__wrapped__(request, 12)

        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(
            any(
                "Annulation — remboursement à effectuer" in call.args[0]
                and "Loyer remboursé au client (90 %) : 90.00 €" in call.args[0]
                and "Loyer conservé par l'agence (10 %) : 10.00 €" in call.args[0]
                and "Caution remboursée intégralement : 50.00 €" in call.args[0]
                and "Total à rembourser au client : 140.00 €" in call.args[0]
                for call in paragraph.call_args_list
            )
        )


class LocationReturnTests(SimpleTestCase):
    def test_closing_location_uses_local_return_date(self):
        returned_on = date(2026, 11, 7)
        location = SimpleNamespace(
            id=12,
            pk=12,
            client="Client test",
            retour_reelle=None,
            statut="en_cours",
            lignes_location=SimpleNamespace(values_list=Mock(return_value=[])),
            penalite_retard=Decimal("0.00"),
            montant_caution_a_rembourser=Decimal("50.00"),
            calculer_penalite_retard=Mock(return_value=Decimal("0.00")),
            save=Mock(),
        )
        request = RequestFactory().post("/locations/12/retourner/")
        request.user = SimpleNamespace(is_superuser=True)

        with (
            patch("core.views.get_object_or_404", return_value=location),
            patch("core.views.timezone.localdate", return_value=returned_on),
            patch("core.views.messages.success"),
            patch("core.views.transaction.atomic"),
            patch("core.views.notify_location_event"),
        ):
            retourner_location.__wrapped__(request, 12)

        self.assertEqual(location.retour_reelle, returned_on)
        self.assertEqual(location.statut, "terminee")


class LocationBusinessRuleTests(SimpleTestCase):
    def test_cancellation_is_allowed_through_24_hours_and_not_after(self):
        created_at = timezone.now()
        location = Location(
            statut="en_cours",
            date_creation=created_at,
            date_debut=date(2026, 11, 1),
            retour_prevue=date(2026, 11, 5),
        )

        with patch(
            "core.models.timezone.now",
            return_value=created_at + timedelta(hours=24),
        ):
            self.assertTrue(location.est_annulable)
        with patch(
            "core.models.timezone.now",
            return_value=created_at + timedelta(hours=24, seconds=1),
        ):
            self.assertFalse(location.est_annulable)

    def test_cancellation_refund_is_90_percent_plus_full_deposit(self):
        location = Location(
            statut="annulee",
            montant_total=Decimal("30.00"),
            caution=Decimal("15.00"),
        )

        self.assertEqual(location.montant_loyer_a_rembourser, Decimal("27.00"))
        self.assertEqual(location.montant_loyer_conserve, Decimal("3.00"))
        self.assertEqual(location.montant_caution_a_rembourser, Decimal("15.00"))
        self.assertEqual(location.montant_total_a_rembourser, Decimal("42.00"))

    def test_return_refunds_only_the_deposit(self):
        location = Location(
            statut="terminee",
            retour_reelle=date(2026, 11, 4),
            montant_total=Decimal("30.00"),
            caution=Decimal("15.00"),
        )

        self.assertEqual(location.montant_loyer_a_rembourser, Decimal("0.00"))
        self.assertEqual(location.montant_caution_a_rembourser, Decimal("15.00"))
        self.assertEqual(location.montant_total_a_rembourser, Decimal("15.00"))

    def test_late_penalties_are_deducted_from_deposit_refund_without_negative_refund(self):
        location = Location(
            statut="terminee",
            retour_reelle=date(2026, 11, 8),
            montant_total=Decimal("100.00"),
            caution=Decimal("50.00"),
            penalite_retard=Decimal("20.00"),
        )
        self.assertEqual(location.montant_caution_a_rembourser, Decimal("30.00"))

        location.penalite_retard = Decimal("60.00")
        self.assertEqual(location.montant_caution_a_rembourser, Decimal("0.00"))

    def test_returned_location_is_displayed_as_completed(self):
        location = Location(
            date_debut=date(2026, 11, 1),
            retour_prevue=date(2026, 11, 5),
            retour_reelle=date(2026, 11, 6),
            statut="en_cours",
        )

        self.assertEqual(location.statut_affiche, "terminee")

    def test_unreturned_location_past_due_is_displayed_as_late(self):
        location = Location(
            date_debut=date(2026, 11, 1),
            retour_prevue=date(2026, 11, 5),
            retour_reelle=None,
            statut="etendue",
        )

        with patch("core.models.timezone.localdate", return_value=date(2026, 11, 6)):
            self.assertEqual(location.statut_affiche, "retard")

    def test_location_total_uses_decimal_arithmetic(self):
        equipment = [
            SimpleNamespace(prix_journalier=Decimal("0.10")),
            SimpleNamespace(prix_journalier=Decimal("0.20")),
        ]

        self.assertEqual(_prix_location(equipment, 3), Decimal("0.90"))

    def test_money_rounding_uses_half_up_for_currency(self):
        self.assertEqual(_arrondir_montant(Decimal("0.045")), Decimal("0.05"))

    def test_late_penalty_is_ten_percent_of_rental_total_per_day(self):
        location = Location(
            retour_prevue=date(2026, 11, 5),
            montant_total=Decimal("100.00"),
        )

        self.assertEqual(
            location.calculer_penalite_retard(date(2026, 11, 8)),
            Decimal("30.00"),
        )

    def test_on_time_return_has_no_late_penalty(self):
        location = Location(
            retour_prevue=date(2026, 11, 5),
            montant_total=Decimal("100.00"),
        )

        self.assertEqual(
            location.calculer_penalite_retard(date(2026, 11, 5)),
            Decimal("0.00"),
        )

    def test_extension_form_rejects_invalid_date(self):
        form = ProlongationLocationForm({"nouvelle_date": "not-a-date"})

        self.assertFalse(form.is_valid())


class LocationLifecycleIntegrationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin", email="admin@example.test", password="test-password"
        )
        self.agence = Agence.objects.create(
            nom="Agence test", ville="Paris", adresse="1 rue test"
        )
        self.categorie = Categorie.objects.create(nom="Informatique")
        self.client_record = Client.objects.create(
            nom="Martin",
            prenom="Alice",
            email="alice@example.test",
            telephone="0102030405",
            agence=self.agence,
        )
        self.equipement = Equipement.objects.create(
            reference="REF-1",
            nom="Ordinateur",
            prix_journalier=Decimal("10.00"),
            categorie=self.categorie,
            agence=self.agence,
        )
        self.client.force_login(self.admin)
        self.today = date.today()

    def creer_location(self, equipement=None, statut="en_cours", retour_reelle=None):
        location = Location.objects.create(
            client=self.client_record,
            agence=self.agence,
            employe=self.admin,
            statut=statut,
            date_debut=self.today,
            retour_prevue=self.today + timedelta(days=3),
            retour_reelle=retour_reelle,
            caution=Decimal("15.00"),
            montant_total=Decimal("30.00"),
            penalite_retard=Decimal("0.00"),
        )
        if equipement:
            LocationEquipement.objects.create(
                location=location,
                equipement=equipement,
                prix_journalier_applique=Decimal("10.00"),
            )
        return location

    def test_return_closes_location_and_releases_equipment_once(self):
        location = self.creer_location(equipement=self.equipement)
        self.equipement.statut = "loue"
        self.equipement.save(update_fields=["statut"])

        response = self.client.post(
            reverse("core:retourner_location", args=[location.pk])
        )
        location.refresh_from_db()
        self.equipement.refresh_from_db()
        return_date = location.retour_reelle

        self.assertEqual(response.status_code, 302)
        self.assertEqual(location.statut, "terminee")
        self.assertEqual(return_date, self.today)
        self.assertEqual(self.equipement.statut, "disponible")

        self.client.post(reverse("core:retourner_location", args=[location.pk]))
        location.refresh_from_db()
        self.assertEqual(location.retour_reelle, return_date)

    def test_location_can_be_cancelled_within_24_hours_and_refund_is_calculated(self):
        location = self.creer_location(equipement=self.equipement)
        self.equipement.statut = "loue"
        self.equipement.save(update_fields=["statut"])
        list_response = self.client.get(reverse("core:liste_locations"))

        self.assertContains(list_response, "Annuler la location")
        self.assertContains(
            list_response, reverse("core:annuler_location", args=[location.pk])
        )

        response = self.client.post(
            reverse("core:annuler_location", args=[location.pk]), follow=True
        )

        location.refresh_from_db()
        self.equipement.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(location.statut, "annulee")
        self.assertEqual(location.montant_total_a_rembourser, Decimal("42.00"))
        self.assertEqual(self.equipement.statut, "disponible")
        self.assertContains(response, "27.00 € sur le loyer")
        self.assertContains(response, "3.00 €")

    def test_cancellation_after_24_hours_is_rejected_and_shown_as_unavailable(self):
        location = self.creer_location(equipement=self.equipement)
        location.date_creation = timezone.now() - timedelta(hours=25)
        location.save(update_fields=["date_creation"])
        self.equipement.statut = "loue"
        self.equipement.save(update_fields=["statut"])

        response = self.client.post(
            reverse("core:annuler_location", args=[location.pk]), follow=True
        )

        location.refresh_from_db()
        self.equipement.refresh_from_db()
        self.assertEqual(location.statut, "en_cours")
        self.assertEqual(self.equipement.statut, "loue")
        self.assertContains(response, "délai de 24 heures est dépassé")
        self.assertContains(response, "Annulation impossible : délai de 24 h dépassé")

    def test_return_message_says_only_the_deposit_is_refunded(self):
        location = self.creer_location(equipement=self.equipement)
        self.equipement.statut = "loue"
        self.equipement.save(update_fields=["statut"])

        response = self.client.post(
            reverse("core:retourner_location", args=[location.pk]), follow=True
        )

        self.assertContains(response, "Caution restante à rembourser : 15.00 €")
        self.assertContains(response, "Aucun remboursement du loyer.")

    def test_creation_rejects_equipment_in_maintenance(self):
        self.equipement.statut = "maintenance"
        self.equipement.save(update_fields=["statut"])

        response = self.client.post(
            reverse("core:creer_location"),
            {
                "client": self.client_record.pk,
                "agence": self.agence.pk,
                "date_debut": self.today.isoformat(),
                "retour_prevue": (self.today + timedelta(days=2)).isoformat(),
                "caution": "10.00",
                "equipements": [self.equipement.pk],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Location.objects.count(), 0)
        self.equipement.refresh_from_db()
        self.assertEqual(self.equipement.statut, "maintenance")

    def test_creation_rejects_equipment_already_linked_to_active_rental(self):
        self.creer_location(equipement=self.equipement)

        response = self.client.post(
            reverse("core:creer_location"),
            {
                "client": self.client_record.pk,
                "agence": self.agence.pk,
                "date_debut": self.today.isoformat(),
                "retour_prevue": (self.today + timedelta(days=2)).isoformat(),
                "caution": "10.00",
                "equipements": [self.equipement.pk],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Location.objects.count(), 1)

    def test_creation_reserves_equipment_and_calculates_amounts(self):
        response = self.client.post(
            reverse("core:creer_location"),
            {
                "client": self.client_record.pk,
                "agence": self.agence.pk,
                "date_debut": self.today.isoformat(),
                "retour_prevue": (self.today + timedelta(days=2)).isoformat(),
                "caution": "10.00",
                "equipements": [self.equipement.pk],
            },
        )

        location = Location.objects.get()
        self.equipement.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(location.montant_total, Decimal("20.00"))
        self.assertEqual(location.caution, Decimal("10.00"))
        self.assertEqual(self.equipement.statut, "loue")

    def test_equipment_in_active_rental_cannot_be_modified_or_deleted(self):
        location = self.creer_location(equipement=self.equipement)
        self.equipement.statut = "loue"
        self.equipement.save(update_fields=["statut"])

        response = self.client.post(
            reverse("core:equipement_modifier", args=[self.equipement.pk]),
            {
                "reference": self.equipement.reference,
                "nom": self.equipement.nom,
                "categorie": self.categorie.pk,
                "agence": self.agence.pk,
                "prix_journalier": "10.00",
                "statut": "disponible",
            },
            follow=True,
        )
        self.equipement.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ne peut pas être modifié")
        self.assertEqual(self.equipement.statut, "loue")
        self.client.post(
            reverse("core:equipement_modifier", args=[self.equipement.pk]),
            {
                "reference": self.equipement.reference,
                "nom": "Nom modifié",
                "categorie": self.categorie.pk,
                "agence": self.agence.pk,
                "prix_journalier": "10.00",
                "statut": "loue",
            },
        )
        self.equipement.refresh_from_db()
        self.assertEqual(self.equipement.nom, "Ordinateur")

        self.client.post(
            reverse("core:equipement_supprimer", args=[self.equipement.pk])
        )
        self.assertTrue(Equipement.objects.filter(pk=self.equipement.pk).exists())
        self.assertTrue(
            LocationEquipement.objects.filter(
                location=location, equipement=self.equipement
            ).exists()
        )

    def test_category_with_equipment_cannot_be_deleted_and_user_is_notified(self):
        response = self.client.post(
            reverse("core:categorie_supprimer", args=[self.categorie.pk]),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Categorie.objects.filter(pk=self.categorie.pk).exists())
        self.assertContains(response, "contient encore des équipements")

    def test_empty_category_deletion_requires_post(self):
        empty_category = Categorie.objects.create(nom="Sans équipement")

        get_response = self.client.get(
            reverse("core:categorie_supprimer", args=[empty_category.pk])
        )
        self.assertEqual(get_response.status_code, 302)
        self.assertTrue(Categorie.objects.filter(pk=empty_category.pk).exists())

        post_response = self.client.post(
            reverse("core:categorie_supprimer", args=[empty_category.pk])
        )
        self.assertEqual(post_response.status_code, 302)
        self.assertFalse(Categorie.objects.filter(pk=empty_category.pk).exists())

    def test_client_list_paginates_ten_and_preserves_filters(self):
        Client.objects.bulk_create(
            [
                Client(
                    nom=f"Client {index}",
                    email=f"client{index}@example.test",
                    telephone="0102030405",
                    agence=self.agence,
                )
                for index in range(11)
            ]
        )

        response = self.client.get(
            reverse("core:liste_clients"),
            {"page": 2, "q": "Client", "sort": "nom"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["clients"]), 1)
        self.assertEqual(response.context["clients"].paginator.per_page, 10)
        self.assertRegex(
            response.content.decode(),
            r'href="\?page=1(?:&amp;|&)q=Client(?:&amp;|&)sort=nom"',
        )

    def test_extension_adds_saved_daily_rate_and_audit_record(self):
        location = self.creer_location(equipement=self.equipement)
        response = self.client.post(
            reverse("core:etendre_location", args=[location.pk]),
            {
                "nouvelle_date": (
                    location.retour_prevue + timedelta(days=2)
                ).isoformat()
            },
        )

        location.refresh_from_db()
        extension = ProlongationLocation.objects.get(location=location)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(location.statut, "etendue")
        self.assertEqual(location.montant_total, Decimal("50.00"))
        self.assertEqual(location.caution, Decimal("25.00"))
        self.assertEqual(extension.montant_supplementaire, Decimal("20.00"))
        self.assertEqual(extension.employe, self.admin)

    def test_extension_after_deadline_adds_ten_percent_penalty_per_late_day(self):
        location = self.creer_location(equipement=self.equipement)
        location.retour_prevue = self.today - timedelta(days=2)
        location.save(update_fields=["retour_prevue"])

        response = self.client.post(
            reverse("core:etendre_location", args=[location.pk]),
            {
                "nouvelle_date": (
                    self.today + timedelta(days=2)
                ).isoformat()
            },
        )

        location.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(location.penalite_retard, Decimal("6.00"))
        self.assertEqual(location.montant_total, Decimal("70.00"))

    def test_late_return_records_ten_percent_penalty_for_each_day(self):
        location = self.creer_location(equipement=self.equipement)
        location.retour_prevue = self.today - timedelta(days=3)
        location.save(update_fields=["retour_prevue"])
        self.equipement.statut = "loue"
        self.equipement.save(update_fields=["statut"])

        self.client.post(reverse("core:retourner_location", args=[location.pk]))

        location.refresh_from_db()
        self.assertEqual(location.penalite_retard, Decimal("9.00"))

    def test_active_location_detail_exposes_extension_form(self):
        location = self.creer_location(equipement=self.equipement)

        response = self.client.get(
            reverse("core:detail_location", args=[location.pk])
        )

        self.assertContains(response, "Prolonger la location")
        self.assertContains(
            response, reverse("core:etendre_location", args=[location.pk])
        )

    def test_employee_from_another_agency_cannot_extend_location(self):
        location = self.creer_location(equipement=self.equipement)
        other_agency = Agence.objects.create(
            nom="Autre agence", ville="Lyon", adresse="2 rue test"
        )
        employee = User.objects.create_user(
            username="employee", password="test-password"
        )
        ProfilEmploye.objects.create(user=employee, agence=other_agency)
        self.client.force_login(employee)

        response = self.client.post(
            reverse("core:etendre_location", args=[location.pk]),
            {
                "nouvelle_date": (
                    location.retour_prevue + timedelta(days=2)
                ).isoformat()
            },
        )

        location.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(location.statut, "en_cours")
        self.assertFalse(ProlongationLocation.objects.filter(location=location).exists())

    def test_existing_rental_can_be_modified_without_changing_its_past_start_date(self):
        location = self.creer_location()
        location.date_debut = self.today - timedelta(days=2)
        location.save(update_fields=["date_debut"])
        form = LocationForm(
            {
                "client": self.client_record.pk,
                "agence": self.agence.pk,
                "date_debut": location.date_debut.isoformat(),
                "retour_prevue": location.retour_prevue.isoformat(),
                "caution": "15.00",
            },
            instance=location,
            user=self.admin,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_invalid_equipment_during_modification_does_not_release_old_equipment(self):
        location = self.creer_location(equipement=self.equipement)
        self.equipement.statut = "loue"
        self.equipement.save(update_fields=["statut"])
        equipment_in_maintenance = Equipement.objects.create(
            reference="REF-2",
            nom="Équipement en maintenance",
            prix_journalier=Decimal("15.00"),
            statut="maintenance",
            categorie=self.categorie,
            agence=self.agence,
        )

        response = self.client.post(
            reverse("core:modifier_location", args=[location.pk]),
            {
                "client": self.client_record.pk,
                "agence": self.agence.pk,
                "date_debut": location.date_debut.isoformat(),
                "retour_prevue": location.retour_prevue.isoformat(),
                "caution": "15.00",
                "equipements": [equipment_in_maintenance.pk],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            LocationEquipement.objects.filter(
                location=location, equipement=self.equipement
            ).exists()
        )
        self.equipement.refresh_from_db()
        self.assertEqual(self.equipement.statut, "loue")

    def test_completed_location_cannot_be_modified_or_deleted(self):
        location = self.creer_location(
            statut="terminee",
            retour_reelle=self.today,
        )

        self.client.post(
            reverse("core:modifier_location", args=[location.pk]),
            {"montant_total": "999.00"},
        )
        self.client.post(reverse("core:supprimer_location", args=[location.pk]))

        self.assertTrue(Location.objects.filter(pk=location.pk).exists())
        location.refresh_from_db()
        self.assertEqual(location.montant_total, Decimal("30.00"))


class CsvExportTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin", email="admin@example.test", password="test-password"
        )
        self.agence = Agence.objects.create(
            nom="Agence test", ville="Paris", adresse="1 rue test"
        )
        self.autre_agence = Agence.objects.create(
            nom="Agence Lyon", ville="Lyon", adresse="2 rue test"
        )
        self.categorie = Categorie.objects.create(nom="Informatique")
        self.client_record = Client.objects.create(
            nom="Martin",
            prenom="Alice",
            email="alice@example.test",
            telephone="0102030405",
            agence=self.agence,
        )
        self.equipement = Equipement.objects.create(
            reference="REF-1",
            nom="Ordinateur",
            prix_journalier=Decimal("10.00"),
            categorie=self.categorie,
            agence=self.agence,
        )
        self.client.force_login(self.admin)
        self.today = timezone.localdate()

    def creer_location(
        self,
        *,
        statut,
        montant_total,
        caution,
        penalite=Decimal("0.00"),
        retour_prevue=None,
        retour_reelle=None,
    ):
        return Location.objects.create(
            client=self.client_record,
            agence=self.agence,
            employe=self.admin,
            statut=statut,
            date_debut=self.today - timedelta(days=3),
            retour_prevue=retour_prevue or self.today + timedelta(days=2),
            retour_reelle=retour_reelle,
            caution=Decimal(caution),
            montant_total=Decimal(montant_total),
            penalite_retard=Decimal(penalite),
        )

    def lire_csv(self, response):
        return list(csv.reader(StringIO(response.content.decode("utf-8-sig"))))

    def test_each_data_list_has_an_export_button(self):
        pages = (
            ("core:liste_equipements", "exporter_equipements_csv"),
            ("core:liste_clients", "exporter_clients_csv"),
            ("core:liste_locations", "exporter_locations_csv"),
            ("core:liste_utilisateurs", "exporter_utilisateurs_csv"),
            ("core:liste_agences", "exporter_agences_csv"),
        )
        for list_name, export_name in pages:
            with self.subTest(page=list_name):
                response = self.client.get(reverse(list_name))
                self.assertContains(response, reverse(f"core:{export_name}"))

    def test_equipment_client_user_and_agency_exports_have_expected_columns(self):
        exports = (
            (
                "core:exporter_equipements_csv",
                [
                    "#ID", "Référence", "Nom", "Prix journalier", "Statut",
                    "Catégorie", "Agence",
                ],
            ),
            (
                "core:exporter_clients_csv",
                ["#ID", "Nom", "Prénom", "Email", "Téléphone", "Agence"],
            ),
            (
                "core:exporter_utilisateurs_csv",
                [
                    "#ID", "Prénom", "Nom", "Identifiant", "Email", "Agence",
                    "Actif", "Date de création",
                ],
            ),
            (
                "core:exporter_agences_csv",
                ["#ID", "Nom", "Ville", "Adresse"],
            ),
        )
        for route_name, expected_headers in exports:
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                rows = self.lire_csv(response)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
                self.assertTrue(
                    response["Content-Disposition"].endswith(".csv\"")
                )
                self.assertEqual(rows[0], expected_headers)
                self.assertGreaterEqual(len(rows), 2)

        user_csv = self.client.get(reverse("core:exporter_utilisateurs_csv"))
        self.assertNotIn("test-password", user_csv.content.decode("utf-8-sig"))

    def test_location_csv_contains_requested_columns_and_settlement_amounts(self):
        cancelled = self.creer_location(
            statut="annulee", montant_total="100.00", caution="50.00"
        )
        normal = self.creer_location(
            statut="terminee",
            montant_total="80.00",
            caution="40.00",
            retour_reelle=self.today,
        )
        late = self.creer_location(
            statut="terminee",
            montant_total="100.00",
            caution="50.00",
            penalite="60.00",
            retour_reelle=self.today,
        )
        active_late = self.creer_location(
            statut="en_cours",
            montant_total="100.00",
            caution="50.00",
            retour_prevue=self.today - timedelta(days=2),
        )

        response = self.client.get(reverse("core:exporter_locations_csv"))
        rows = self.lire_csv(response)
        self.assertEqual(
            rows[0],
            [
                "#ID", "Client", "Agence", "Période", "Montant Total",
                "Remboursement", "Caution déposée", "Montant Final",
            ],
        )
        by_id = {int(row[0]): row for row in rows[1:]}
        self.assertEqual(by_id[cancelled.pk][5:], ["140.00", "50.00", "10.00"])
        self.assertEqual(by_id[normal.pk][5:], ["40.00", "40.00", "80.00"])
        self.assertEqual(by_id[late.pk][5:], ["0.00", "50.00", "160.00"])
        self.assertEqual(by_id[active_late.pk][5:], ["30.00", "50.00", "120.00"])

    def test_employee_exports_only_data_from_their_agency(self):
        Client.objects.create(
            nom="Durand",
            prenom="Bob",
            email="bob@example.test",
            telephone="0102030406",
            agence=self.autre_agence,
        )
        Equipement.objects.create(
            reference="REF-2",
            nom="Tablette",
            prix_journalier=Decimal("15.00"),
            categorie=self.categorie,
            agence=self.autre_agence,
        )
        employee = User.objects.create_user(
            username="employee", password="test-password"
        )
        ProfilEmploye.objects.create(user=employee, agence=self.agence)
        self.client.force_login(employee)

        for route_name in (
            "core:exporter_clients_csv",
            "core:exporter_equipements_csv",
            "core:exporter_locations_csv",
        ):
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                exported = response.content.decode("utf-8-sig")
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("Agence Lyon", exported)
                self.assertNotIn("Durand", exported)
                self.assertNotIn("REF-2", exported)

        denied_users_export = self.client.get(
            reverse("core:exporter_utilisateurs_csv")
        )
        self.assertEqual(denied_users_export.status_code, 302)


class NotificationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin", email="admin@example.test", password="test-password"
        )
        self.agence = Agence.objects.create(
            nom="Agence test", ville="Paris", adresse="1 rue test"
        )
        self.autre_agence = Agence.objects.create(
            nom="Agence Lyon", ville="Lyon", adresse="2 rue test"
        )
        self.employee = User.objects.create_user(
            username="employee", password="test-password"
        )
        ProfilEmploye.objects.create(user=self.employee, agence=self.agence)
        self.other_employee = User.objects.create_user(
            username="other_employee", password="test-password"
        )
        ProfilEmploye.objects.create(
            user=self.other_employee, agence=self.autre_agence
        )
        self.categorie = Categorie.objects.create(nom="Informatique")
        self.client_record = Client.objects.create(
            nom="Martin",
            prenom="Alice",
            email="alice@example.test",
            telephone="0102030405",
            agence=self.agence,
        )
        self.equipement = Equipement.objects.create(
            reference="REF-1",
            nom="Ordinateur",
            prix_journalier=Decimal("10.00"),
            categorie=self.categorie,
            agence=self.agence,
        )
        self.today = date(2026, 11, 9)

    def creer_location(self, retour_prevue, statut="en_cours"):
        return Location.objects.create(
            client=self.client_record,
            agence=self.agence,
            employe=self.employee,
            statut=statut,
            date_debut=self.today,
            retour_prevue=retour_prevue,
            caution=Decimal("15.00"),
            montant_total=Decimal("30.00"),
        )

    def test_employee_location_event_notifies_admins_but_not_agency_users(self):
        from .notifications import notify_location_event

        location = self.creer_location(self.today + timedelta(days=2))
        notify_location_event(
            location,
            self.employee,
            "location_created",
            "Nouvelle location",
            "Une location a été créée.",
        )

        notifications = Notification.objects.all()
        self.assertEqual(notifications.count(), 1)
        self.assertSetEqual(
            set(notifications.values_list("recipient_id", flat=True)),
            {self.admin.pk},
        )
        admin_notification = notifications.get(recipient=self.admin)
        self.assertEqual(admin_notification.actor, self.employee)
        self.assertEqual(admin_notification.agence, self.agence)
        self.assertIn("employee", admin_notification.message)
        self.assertEqual(
            admin_notification.target_url,
            reverse("core:detail_location", args=[location.pk]),
        )

    def test_notification_icon_page_read_action_and_recipient_isolation(self):
        notification = Notification.objects.create(
            recipient=self.employee,
            actor=self.admin,
            agence=self.agence,
            event_type="equipment_created",
            title="Nouvel équipement",
            message="Équipement ajouté au stock.",
            target_url=reverse("core:liste_equipements"),
            event_key="equipment:1",
        )
        self.client.force_login(self.employee)

        page = self.client.get(reverse("core:liste_notifications"))
        self.assertContains(page, "Nouvel équipement")
        self.assertContains(page, "admin")
        self.assertContains(page, "Agence test")
        self.assertContains(
            page,
            reverse("core:ouvrir_notification", args=[notification.pk]),
        )
        self.assertContains(page, 'aria-label="Notifications"')
        self.assertEqual(page.context["unread_notifications_count"], 1)

        response = self.client.post(
            reverse("core:ouvrir_notification", args=[notification.pk])
        )
        notification.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("core:liste_equipements"))
        self.assertIsNotNone(notification.read_at)

        self.client.force_login(self.other_employee)
        forbidden = self.client.post(
            reverse("core:ouvrir_notification", args=[notification.pk])
        )
        self.assertEqual(forbidden.status_code, 404)

    def test_daily_reminders_are_scoped_and_idempotent(self):
        tomorrow = self.creer_location(self.today + timedelta(days=1))
        due_today = self.creer_location(self.today)
        overdue = self.creer_location(self.today - timedelta(days=1))
        self.creer_location(self.today + timedelta(days=5))
        self.creer_location(
            self.today - timedelta(days=1),
            statut="terminee",
        )
        with patch(
            "core.management.commands.envoyer_rappels_echeance.timezone.localdate",
            return_value=self.today,
        ):
            call_command("envoyer_rappels_echeance", stdout=StringIO())
            call_command("envoyer_rappels_echeance", stdout=StringIO())

        notifications = Notification.objects.order_by("event_type", "recipient_id")
        self.assertEqual(notifications.count(), 6)
        self.assertEqual(
            set(notifications.values_list("recipient_id", flat=True)),
            {self.admin.pk, self.employee.pk},
        )
        self.assertEqual(
            set(notifications.values_list("event_type", flat=True)),
            {"rental_due_tomorrow", "rental_due_today", "rental_overdue"},
        )
        self.assertTrue(
            notifications.filter(
                title="Location en retard",
                message__contains=f"#{overdue.pk}",
            ).exists()
        )
        self.assertTrue(
            notifications.filter(message__contains=f"#{tomorrow.pk}").exists()
        )
        self.assertTrue(
            notifications.filter(message__contains=f"#{due_today.pk}").exists()
        )

    def test_new_equipment_assignment_notifies_the_agency(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("core:equipement_ajouter"),
            {
                "reference": "REF-NEW",
                "nom": "Nouveau matériel",
                "prix_journalier": "20.00",
                "statut": "disponible",
                "categorie": self.categorie.pk,
                "agence": self.agence.pk,
            },
        )

        self.assertEqual(response.status_code, 302)
        notification = Notification.objects.get(recipient=self.employee)
        self.assertEqual(notification.event_type, "equipment_created")
        self.assertEqual(notification.agence, self.agence)
        self.assertIn("REF-NEW", notification.message)
        self.assertFalse(
            Notification.objects.filter(recipient=self.other_employee).exists()
        )

    def test_equipment_maintenance_change_notifies_its_agency(self):
        from .notifications import notify_equipment_event

        self.client.force_login(self.admin)
        with patch(
            "core.views.notify_equipment_event",
            wraps=notify_equipment_event,
        ) as notify:
            response = self.client.post(
                reverse("core:equipement_modifier", args=[self.equipement.pk]),
                {
                    "reference": self.equipement.reference,
                    "nom": self.equipement.nom,
                    "prix_journalier": "10.00",
                    "statut": "maintenance",
                    "categorie": self.categorie.pk,
                    "agence": self.agence.pk,
                },
            )

        self.assertEqual(response.status_code, 302)
        self.equipement.refresh_from_db()
        self.assertEqual(self.equipement.statut, "maintenance")
        self.assertTrue(notify.called)
        notification = Notification.objects.get(recipient=self.employee)
        self.assertEqual(notification.event_type, "equipment_updated")
        self.assertIn("maintenance", notification.message)
        self.assertFalse(
            Notification.objects.filter(recipient=self.other_employee).exists()
        )

    def test_employee_location_creation_notifies_admin_only(self):
        self.client.force_login(self.employee)
        response = self.client.post(
            reverse("core:creer_location"),
            {
                "client": self.client_record.pk,
                "agence": self.agence.pk,
                "date_debut": self.today.isoformat(),
                "retour_prevue": (self.today + timedelta(days=2)).isoformat(),
                "caution": "15.00",
                "equipements": [self.equipement.pk],
            },
        )

        self.assertEqual(response.status_code, 302)
        notifications = Notification.objects.filter(event_type="location_created")
        self.assertSetEqual(
            set(notifications.values_list("recipient_id", flat=True)),
            {self.admin.pk},
        )
        self.assertEqual(notifications.first().agence, self.agence)
        self.assertFalse(
            Notification.objects.filter(recipient=self.employee).exists()
        )
        self.assertFalse(
            Notification.objects.filter(recipient=self.other_employee).exists()
        )

    def test_admin_action_notifies_only_target_agency_employees_and_other_admins(self):
        from .notifications import notify_location_event

        location = self.creer_location(self.today + timedelta(days=2))
        notify_location_event(
            location,
            self.admin,
            "location_cancelled",
            "Location annulée",
            "Annulation réalisée par l’administration.",
        )

        self.assertSetEqual(
            set(Notification.objects.values_list("recipient_id", flat=True)),
            {self.employee.pk},
        )
        self.assertFalse(
            Notification.objects.filter(recipient=self.admin).exists()
        )
        self.assertFalse(
            Notification.objects.filter(recipient=self.other_employee).exists()
        )
