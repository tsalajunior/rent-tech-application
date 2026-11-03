from django.template.loader import get_template
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve, reverse
from types import SimpleNamespace
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from .views import liste_locations, telecharger_location_pdf


class LocationUrlTests(SimpleTestCase):
    def test_legacy_location_list_url_resolves(self):
        match = resolve("/liste_locations/")

        self.assertEqual(match.func, liste_locations)

    def test_named_location_list_url_remains_canonical(self):
        self.assertEqual(reverse("core:liste_locations"), "/locations/")

    def test_location_pdf_url_resolves(self):
        self.assertEqual(
            resolve("/locations/12/pdf/").func, telecharger_location_pdf
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
                    lignes_location=SimpleNamespace(all=lambda: []),
                    montant_total=Decimal("100.00"),
                    caution=Decimal("50.00"),
                )
            }
        )

        self.assertIn("Générer le PDF", html)
        self.assertIn(reverse("core:telecharger_location_pdf", args=[12]), html)

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
    def test_pdf_download_returns_a_pdf_attachment(self):
        location = SimpleNamespace(
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
            caution=Decimal("50.00"),
        )
        request = RequestFactory().get("/locations/12/pdf/")
        request.user = SimpleNamespace(is_superuser=True)

        with patch("core.views.get_object_or_404", return_value=location):
            response = telecharger_location_pdf.__wrapped__(request, 12)

        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(
            response["Content-Disposition"],
            'attachment; filename="location-12.pdf"',
        )
        self.assertTrue(response.content.startswith(b"%PDF-"))
