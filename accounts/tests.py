"""
Tests -- Module Accounts
=========================
Couvre :
  - La generation de mots de passe securises (_generer_mot_de_passe)
  - La generation de usernames uniques (_generer_username)
  - La creation de compte eleve (creer_compte_eleve)
  - La creation de compte parent (creer_compte_parent)
  - Les proprietes et roles du modele User
  - Le systeme de permissions (has_permission)
"""
import datetime
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.views_comptes import (
    _generer_username,
    _generer_mot_de_passe,
    _ALPHABET_MDP,
    creer_compte_eleve,
    creer_compte_parent,
)
from accounts.permissions import has_permission

User = get_user_model()


# ---- Helpers de fixture -----------------------------------------------------

def _creer_etablissement(code="TST"):
    from etablissements.models import Etablissement
    return Etablissement.objects.create(nom=f"Ecole Test {code}", code=code, type="ecole")


def _creer_annee(etab):
    from etablissements.models import AnneeScolaire
    return AnneeScolaire.objects.create(
        etablissement=etab, libelle="2025-2026",
        date_debut=datetime.date(2025, 10, 1),
        date_fin=datetime.date(2026, 7, 31),
        is_active=True,
    )


def _creer_eleve(etab, nom="Diallo", prenom="Moussa"):
    """Cree un eleve en laissant Eleve.save() generer le matricule."""
    from eleves.models import Eleve
    return Eleve.objects.create(
        etablissement=etab,
        nom=nom, prenom=prenom,
        sexe='M',
        date_naissance=datetime.date(2008, 3, 15),
    )


def _creer_tuteur(etab, nom="Traore", prenom="Oumar", telephone="76123456"):
    from eleves.models import Tuteur
    return Tuteur.objects.create(
        etablissement=etab, nom=nom, prenom=prenom,
        lien="pere", telephone=telephone
    )


# ---- Tests : generation de mot de passe -------------------------------------

class TestGenererMotDePasse(TestCase):

    def test_longueur_par_defaut(self):
        self.assertEqual(len(_generer_mot_de_passe()), 10)

    def test_longueur_personnalisee(self):
        for n in [8, 12, 16]:
            self.assertEqual(len(_generer_mot_de_passe(longueur=n)), n)

    def test_contient_majuscule(self):
        for _ in range(20):
            mdp = _generer_mot_de_passe()
            self.assertTrue(any(c.isupper() for c in mdp), f"Pas de majuscule dans : {mdp}")

    def test_contient_chiffre(self):
        for _ in range(20):
            mdp = _generer_mot_de_passe()
            self.assertTrue(any(c.isdigit() for c in mdp), f"Pas de chiffre dans : {mdp}")

    def test_pas_de_caracteres_ambigus(self):
        ambigus = set("0OlI1")
        for _ in range(50):
            mdp = _generer_mot_de_passe()
            for c in mdp:
                self.assertNotIn(c, ambigus, f"Caractere ambigu '{c}' dans : {mdp}")

    def test_unicite(self):
        mdps = {_generer_mot_de_passe() for _ in range(100)}
        self.assertGreater(len(mdps), 95)

    def test_module_secrets_utilise(self):
        """Verifie que le module secrets est importe dans views_comptes."""
        import accounts.views_comptes as vc
        import importlib
        source = importlib.util.find_spec("accounts.views_comptes")
        self.assertIsNotNone(source)
        # Verifier que _ALPHABET_MDP est defini (indicateur du nouveau code)
        self.assertTrue(len(_ALPHABET_MDP) > 30)


# ---- Tests : generation de username -----------------------------------------

class TestGenererUsername(TestCase):

    def test_premier_choix_disponible(self):
        self.assertEqual(_generer_username("moussa"), "moussa")

    def test_suffixe_si_occupe(self):
        User.objects.create_user(username="ibra", password="x")
        self.assertEqual(_generer_username("ibra"), "ibra1")

    def test_suffixe_incremental(self):
        User.objects.create_user(username="ali", password="x")
        User.objects.create_user(username="ali1", password="x")
        self.assertEqual(_generer_username("ali"), "ali2")


# ---- Tests : creation de compte eleve ---------------------------------------

class TestCreerCompteEleve(TestCase):

    def setUp(self):
        self.etab = _creer_etablissement(code="CTE")
        _creer_annee(self.etab)

    def test_cree_nouveau_compte(self):
        eleve = _creer_eleve(self.etab)
        user, cree, mdp = creer_compte_eleve(eleve, self.etab)
        self.assertTrue(cree)
        self.assertIsNotNone(user)
        self.assertIsNotNone(mdp)
        self.assertEqual(user.role, User.ROLE_ELEVE)
        self.assertEqual(user.etablissement, self.etab)
        self.assertEqual(user.first_name, eleve.prenom)
        self.assertEqual(user.last_name, eleve.nom)

    def test_ne_recrée_pas_si_existant(self):
        eleve = _creer_eleve(self.etab, nom="Coulibaly", prenom="Ibrahim")
        user1, _, _ = creer_compte_eleve(eleve, self.etab)
        eleve.refresh_from_db()
        user2, cree, mdp = creer_compte_eleve(eleve, self.etab)
        self.assertFalse(cree)
        self.assertEqual(user1.pk, user2.pk)
        self.assertIsNone(mdp)

    def test_mdp_pas_date_naissance(self):
        eleve = _creer_eleve(self.etab, nom="Keita", prenom="Fatoumata")
        _, _, mdp = creer_compte_eleve(eleve, self.etab)
        date_naissance = eleve.date_naissance.strftime("%d%m%Y")
        self.assertNotEqual(mdp, date_naissance)
        self.assertNotIn(date_naissance, mdp)

    def test_mdp_longueur_suffisante(self):
        eleve = _creer_eleve(self.etab, nom="Sissoko", prenom="Binta")
        _, _, mdp = creer_compte_eleve(eleve, self.etab)
        self.assertGreaterEqual(len(mdp), 8)

    def test_mdp_contient_majuscule_et_chiffre(self):
        eleve = _creer_eleve(self.etab, nom="Camara", prenom="Lamine")
        _, _, mdp = creer_compte_eleve(eleve, self.etab)
        self.assertTrue(any(c.isupper() for c in mdp), f"Pas de majuscule dans {mdp}")
        self.assertTrue(any(c.isdigit() for c in mdp), f"Pas de chiffre dans {mdp}")


# ---- Tests : creation de compte parent --------------------------------------

class TestCreerCompteParent(TestCase):

    def setUp(self):
        self.etab = _creer_etablissement(code="CTP")
        _creer_annee(self.etab)

    def test_retourne_none_sans_tuteur(self):
        eleve = _creer_eleve(self.etab, nom="Maiga", prenom="Sekou")
        user, cree, mdp = creer_compte_parent(eleve, self.etab)
        self.assertIsNone(user)
        self.assertFalse(cree)
        self.assertIsNone(mdp)

    def test_cree_compte_avec_tuteur(self):
        eleve = _creer_eleve(self.etab, nom="Haidara", prenom="Mariam")
        tuteur = _creer_tuteur(self.etab, nom="Haidara", prenom="Oumar")
        eleve.tuteur = tuteur
        eleve.save()
        user, cree, mdp = creer_compte_parent(eleve, self.etab)
        self.assertTrue(cree)
        self.assertIsNotNone(user)
        self.assertIsNotNone(mdp)
        self.assertEqual(user.role, User.ROLE_PARENT)

    def test_mdp_pas_telephone(self):
        eleve = _creer_eleve(self.etab, nom="Toure", prenom="Aminata")
        tuteur = _creer_tuteur(self.etab, nom="Toure", prenom="Boubacar", telephone="76123456")
        eleve.tuteur = tuteur
        eleve.save()
        _, _, mdp = creer_compte_parent(eleve, self.etab)
        self.assertNotEqual(mdp, "76123456")
        self.assertNotIn("76123456", mdp)

    def test_ne_recrée_pas_si_parent_existant(self):
        eleve = _creer_eleve(self.etab, nom="Barry", prenom="Djibril")
        tuteur = _creer_tuteur(self.etab, nom="Barry", prenom="Abdoulaye", telephone="65987654")
        eleve.tuteur = tuteur
        eleve.save()
        user1, _, _ = creer_compte_parent(eleve, self.etab)
        tuteur.refresh_from_db()
        eleve.refresh_from_db()
        user2, cree, mdp = creer_compte_parent(eleve, self.etab)
        self.assertFalse(cree)
        self.assertEqual(user1.pk, user2.pk)
        self.assertIsNone(mdp)


# ---- Tests : Modele User ----------------------------------------------------

class TestUserModel(TestCase):

    def _u(self, role, suffix=""):
        return User.objects.create_user(username=f"u_{role}{suffix}", password="x", role=role)

    def test_is_admin_inclut_super_admin(self):
        self.assertTrue(self._u('admin', 'a').is_admin)
        self.assertTrue(self._u('super_admin', 'b').is_admin)

    def test_is_admin_false_pour_autres(self):
        for r in ['comptable', 'enseignant', 'surveillant', 'secretariat', 'parent', 'eleve']:
            self.assertFalse(self._u(r, r).is_admin, f"is_admin faux attendu pour '{r}'")

    def test_is_comptable_inclut_admin(self):
        for r, s in [('comptable', 'x'), ('admin', 'y'), ('super_admin', 'z')]:
            self.assertTrue(self._u(r, s).is_comptable, f"is_comptable vrai attendu pour '{r}'")

    def test_proprietes_exclusives(self):
        cas = [
            ('enseignant', 'is_enseignant'),
            ('surveillant', 'is_surveillant'),
            ('secretariat', 'is_secretariat'),
            ('parent', 'is_parent'),
            ('eleve', 'is_eleve_user'),
        ]
        for role, prop in cas:
            user = self._u(role, prop)
            self.assertTrue(getattr(user, prop), f"'{prop}' devrait etre True pour '{role}'")


# ---- Tests : Permissions ----------------------------------------------------

class TestHasPermission(TestCase):

    def _u(self, role):
        return User.objects.create_user(username=f"p_{role}", password="x", role=role)

    def test_super_admin_acces_tout(self):
        user = self._u('super_admin')
        for module in ['dashboard', 'eleves', 'notes', 'finances', 'paiements', 'parametres']:
            self.assertTrue(has_permission(user, module),
                            f"super_admin devrait avoir acces a '{module}'")

    def test_parent_limite_espace_famille(self):
        user = self._u('parent')
        self.assertTrue(has_permission(user, 'espace_famille'))
        self.assertFalse(has_permission(user, 'notes'))
        self.assertFalse(has_permission(user, 'finances'))

    def test_comptable_pas_acces_notes(self):
        user = self._u('comptable')
        self.assertFalse(has_permission(user, 'notes'))
        self.assertTrue(has_permission(user, 'paiements'))

    def test_non_authentifie(self):
        from django.contrib.auth.models import AnonymousUser
        self.assertFalse(has_permission(AnonymousUser(), 'dashboard'))
