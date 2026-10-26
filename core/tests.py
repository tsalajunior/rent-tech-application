from django.template.loader import get_template
from django.test import SimpleTestCase
from django.urls import resolve, reverse
from types import SimpleNamespace

from .views import liste_locations


class LocationUrlTests(SimpleTestCase):
    def test_legacy_location_list_url_resolves(self):
        match = resolve("/liste_locations/")

        self.assertEqual(match.func, liste_locations)

    def test_named_location_list_url_remains_canonical(self):
        self.assertEqual(reverse("core:liste_locations"), "/locations/")


class LocationTemplateTests(SimpleTestCase):
    def test_location_templates_are_loadable(self):
        get_template("core/pages/liste_locations.html")
        get_template("core/pages/location_form.html")

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
