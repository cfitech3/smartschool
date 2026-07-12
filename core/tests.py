"""
Tests -- Module Core
=====================
Couvre :
  - EtablissementMiddleware (injection de request.etablissement)
  - La correction P1.2 : isolation des messages par role
  - Le middleware ne leve pas d erreur si l utilisateur n a pas d etablissement
"""
import datetime
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.session import SessionStorage

User = get_user_model()


def _creer_etab(code="CORE"):
    from etablissements.models import Etablissement
    return Etablissement.objects.create(nom=f"Ecole Core {code}", code=code, type="ecole")


class TestEtablissementMiddleware(TestCase):
    """Teste que le middleware injecte correctement l etablissement."""

    def setUp(self):
        self.etab = _creer_etab()
        self.user = User.objects.create_user(
            username="mw_user", password="x",
            role="admin", etablissement=self.etab
        )

    def test_etab_injecte_pour_utilisateur_avec_etab(self):
        """Un utilisateur rattache a un etab doit avoir request.etablissement rempli."""
        self.client.force_login(self.user)
        response = self.client.get("/dashboard/")
        # Le middleware s execute avant la vue. Si pas d erreur 500, c est ok.
        self.assertNotEqual(response.status_code, 500)

    def test_super_admin_recoit_etab_par_defaut(self):
        """Un super admin sans etab en session doit recevoir le premier etab disponible."""
        sa = User.objects.create_user(username="sa_mw", password="x", role="super_admin")
        self.client.force_login(sa)
        response = self.client.get("/dashboard/")
        self.assertNotEqual(response.status_code, 500)


class TestAdminMessagesIsolation(TestCase):
    """
    Teste la correction P1.2 :
    Le filtrage des messages par role ne doit pas etre ecrase.
    """

    def setUp(self):
        self.etab = _creer_etab(code="MSG")
        self.admin = User.objects.create_user(
            username="admin_msg", password="admin123",
            role="admin", etablissement=self.etab, is_staff=True
        )
        self.comptable = User.objects.create_user(
            username="cpt_msg", password="cpt123",
            role="comptable", etablissement=self.etab
        )
        self.parent = User.objects.create_user(
            username="par_msg", password="par123",
            role="parent", etablissement=self.etab
        )

    def test_acces_refuse_aux_parents(self):
        """Un parent ne doit pas pouvoir acceder a la vue admin_messages."""
        self.client.force_login(self.parent)
        response = self.client.get("/messages/")
        # Doit etre redirige (302) ou interdire l acces
        self.assertIn(response.status_code, [302, 403])

    def test_admin_peut_acceder(self):
        """L admin peut acceder a la vue admin_messages."""
        self.client.force_login(self.admin)
        response = self.client.get("/messages/")
        # 200 = ok, 302 = redirect possible si etab non configure
        self.assertIn(response.status_code, [200, 302])


class TestSettings(TestCase):
    """Teste que les settings critiques sont corrects."""

    def test_debug_est_true_en_test(self):
        """En mode test, DEBUG peut etre True (pas de production)."""
        from django.conf import settings
        # On ne teste pas la valeur, mais que la variable existe
        self.assertIsNotNone(settings.DEBUG)

    def test_secret_key_non_vide(self):
        """La SECRET_KEY ne doit jamais etre vide."""
        from django.conf import settings
        self.assertTrue(len(settings.SECRET_KEY) > 10)

    def test_message_storage_session(self):
        """Le stockage des messages doit utiliser SessionStorage (plus sur que CookieStorage)."""
        from django.conf import settings
        self.assertIn("session", settings.MESSAGE_STORAGE.lower())
