import datetime
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from etablissements.models import Etablissement, AnneeScolaire
from finances.models import Paiement, TypeFrais

User = get_user_model()


class TestDashboardSaasEtIsolation(TestCase):
    def setUp(self):
        self.etab = Etablissement.objects.create(nom="Lycée Alpha", code="ALPHA", type="lycee")
        self.annee = AnneeScolaire.objects.create(
            etablissement=self.etab, libelle="2025-2026",
            date_debut=datetime.date(2025, 10, 1),
            date_fin=datetime.date(2026, 7, 31),
            is_active=True,
        )
        self.superadmin = User.objects.create_user(
            username="sa_test", password="Password1234!", role="super_admin"
        )
        self.admin_etab = User.objects.create_user(
            username="dir_alpha", password="Password1234!", role="admin", etablissement=self.etab
        )

    def test_dashboard_saas_refuse_non_superadmin(self):
        self.client.force_login(self.admin_etab)
        resp = self.client.get(reverse("dashboard_saas"))
        self.assertEqual(resp.status_code, 302)

    def test_dashboard_saas_ok_et_12_mois_uniques(self):
        self.client.force_login(self.superadmin)
        resp = self.client.get(reverse("dashboard_saas"))
        self.assertEqual(resp.status_code, 200)
        import json
        chart = json.loads(resp.context["chart_croissance"])
        self.assertEqual(len(chart), 12)
        mois_labels = [c["mois"] for c in chart]
        self.assertEqual(len(set(mois_labels)), 12)
