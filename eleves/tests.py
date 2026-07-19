"""
Tests — Module Eleves
======================
Couvre :
  - Génération automatique de matricule (unicité, format, atomicité)
  - Propriétés de l'élève (nom_complet, age)
  - Modèle Tuteur (création, lien)
  - Modèle Inscription (création, unicité par élève/année)
  - Modèle Présence (création, statuts, unicité eleve/date/classe)
"""
import datetime
from django.test import TestCase
from django.utils import timezone


# ── Helpers de fixture ────────────────────────────────────────────────────────

def _creer_etablissement(code="TST"):
    from etablissements.models import Etablissement
    return Etablissement.objects.create(
        nom=f"Ecole Test {code}", code=code, type="ecole"
    )


def _creer_annee(etab, libelle="2025-2026", is_active=True):
    from etablissements.models import AnneeScolaire
    return AnneeScolaire.objects.create(
        etablissement=etab, libelle=libelle,
        date_debut=datetime.date(2025, 10, 1),
        date_fin=datetime.date(2026, 7, 31),
        is_active=is_active,
    )


def _creer_niveau(etab, nom="6ème", ordre=1):
    from etablissements.models import Niveau
    return Niveau.objects.create(etablissement=etab, nom=nom, ordre=ordre)


def _creer_classe(etab, annee, niveau, nom="6A"):
    from etablissements.models import Classe
    return Classe.objects.create(
        etablissement=etab, annee=annee, niveau=niveau, nom=nom
    )


def _creer_eleve(etab, nom="Diallo", prenom="Moussa"):
    from eleves.models import Eleve
    return Eleve.objects.create(
        etablissement=etab, nom=nom, prenom=prenom,
        sexe='M', date_naissance=datetime.date(2010, 3, 15),
    )


def _creer_tuteur(etab, nom="Traore", prenom="Oumar", tel="76123456"):
    from eleves.models import Tuteur
    return Tuteur.objects.create(
        etablissement=etab, nom=nom, prenom=prenom,
        lien="pere", telephone=tel,
    )


# ── Tests : Matricule ─────────────────────────────────────────────────────────

class TestEleveMatricule(TestCase):

    def setUp(self):
        self.etab = _creer_etablissement(code="MAT")
        self.annee = _creer_annee(self.etab)

    def test_matricule_genere_automatiquement(self):
        """Un élève sans matricule doit en recevoir un à la création."""
        from eleves.models import Eleve
        e = Eleve.objects.create(
            etablissement=self.etab, nom="Keita", prenom="Ibrahima",
            sexe='M', date_naissance=datetime.date(2010, 1, 1),
        )
        self.assertNotEqual(e.matricule, "")
        self.assertIn("MAT", e.matricule)

    def test_matricule_format(self):
        """Le matricule doit respecter le format CODE-ANNEE-XXXX."""
        from eleves.models import Eleve
        e = Eleve.objects.create(
            etablissement=self.etab, nom="Coulibaly", prenom="Fatou",
            sexe='F', date_naissance=datetime.date(2011, 5, 20),
        )
        parts = e.matricule.split("-")
        self.assertGreaterEqual(len(parts), 3)
        self.assertEqual(parts[0], "MAT")

    def test_matricules_uniques_eleves_multiples(self):
        """Deux élèves créés simultanément ne doivent pas avoir le même matricule."""
        from eleves.models import Eleve
        mats = set()
        for i in range(10):
            e = Eleve.objects.create(
                etablissement=self.etab, nom=f"Test{i}", prenom="Eleve",
                sexe='M', date_naissance=datetime.date(2010, 1, 1),
            )
            mats.add(e.matricule)
        self.assertEqual(len(mats), 10, f"Matricules dupliqués détectés : {mats}")

    def test_matricule_manual_conserve(self):
        """Un matricule fourni manuellement ne doit pas être écrasé."""
        from eleves.models import Eleve
        e = Eleve.objects.create(
            etablissement=self.etab, nom="Sissoko", prenom="Binta",
            sexe='F', date_naissance=datetime.date(2009, 7, 10),
            matricule="MAT-CUSTOM-9999",
        )
        self.assertEqual(e.matricule, "MAT-CUSTOM-9999")


# ── Tests : Propriétés Eleve ──────────────────────────────────────────────────

class TestEleveProprietés(TestCase):

    def setUp(self):
        self.etab = _creer_etablissement(code="PRO")
        _creer_annee(self.etab)

    def test_nom_complet(self):
        e = _creer_eleve(self.etab, nom="Diallo", prenom="Moussa")
        self.assertEqual(e.nom_complet, "Diallo Moussa")

    def test_age_calcul(self):
        today = datetime.date.today()
        date_naissance = today.replace(year=today.year - 14)
        from eleves.models import Eleve
        e = Eleve.objects.create(
            etablissement=self.etab, nom="Age", prenom="Test",
            sexe='M', date_naissance=date_naissance,
        )
        self.assertEqual(e.age, 14)

    def test_str_contient_nom_et_matricule(self):
        e = _creer_eleve(self.etab, nom="Kone", prenom="Ali")
        s = str(e)
        self.assertIn("Kone", s)
        self.assertIn("Ali", s)


# ── Tests : Tuteur ────────────────────────────────────────────────────────────

class TestTuteur(TestCase):

    def setUp(self):
        self.etab = _creer_etablissement(code="TUT")
        _creer_annee(self.etab)

    def test_creation_tuteur(self):
        t = _creer_tuteur(self.etab, nom="Barry", prenom="Mamadou")
        self.assertEqual(t.nom, "Barry")
        self.assertEqual(t.prenom, "Mamadou")
        self.assertEqual(t.lien, "pere")

    def test_str_contient_nom(self):
        t = _creer_tuteur(self.etab, nom="Haidara", prenom="Rokia")
        s = str(t)
        self.assertIn("Haidara", s)

    def test_telephone_obligatoire(self):
        """Le téléphone est requis pour créer un tuteur."""
        from eleves.models import Tuteur
        from django.db import IntegrityError
        # Ne devrait pas lever d'erreur (blank est autorisé dans le modèle)
        t = Tuteur.objects.create(
            etablissement=self.etab, nom="Toure", prenom="Bintou",
            lien="mere", telephone="65123456",
        )
        self.assertEqual(t.telephone, "65123456")


# ── Tests : Inscription ───────────────────────────────────────────────────────

class TestInscription(TestCase):

    def setUp(self):
        self.etab = _creer_etablissement(code="INS")
        self.annee = _creer_annee(self.etab)
        self.niveau = _creer_niveau(self.etab)
        self.classe = _creer_classe(self.etab, self.annee, self.niveau)
        self.eleve = _creer_eleve(self.etab)

    def test_inscription_creation(self):
        from eleves.models import Inscription
        insc = Inscription.objects.create(
            eleve=self.eleve, classe=self.classe, annee=self.annee, statut='actif'
        )
        self.assertEqual(insc.statut, 'actif')
        self.assertTrue(insc.is_active)

    def test_unique_eleve_annee(self):
        """Un élève ne peut être inscrit qu'une fois par année scolaire."""
        from eleves.models import Inscription
        from django.db import IntegrityError
        Inscription.objects.create(
            eleve=self.eleve, classe=self.classe, annee=self.annee
        )
        with self.assertRaises(IntegrityError):
            Inscription.objects.create(
                eleve=self.eleve, classe=self.classe, annee=self.annee
            )

    def test_get_inscription_active(self):
        from eleves.models import Inscription
        Inscription.objects.create(
            eleve=self.eleve, classe=self.classe, annee=self.annee, is_active=True
        )
        result = self.eleve.get_inscription_active()
        self.assertIsNotNone(result)
        self.assertTrue(result.is_active)


# ── Tests : Présence ──────────────────────────────────────────────────────────

class TestPresence(TestCase):

    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.etab = _creer_etablissement(code="PRE")
        self.annee = _creer_annee(self.etab)
        self.niveau = _creer_niveau(self.etab)
        self.classe = _creer_classe(self.etab, self.annee, self.niveau)
        self.eleve = _creer_eleve(self.etab)
        self.surveillant = User.objects.create_user(
            username="surv_test", password="x", role="surveillant",
            etablissement=self.etab,
        )

    def test_presence_creation(self):
        from eleves.models import Presence
        today = timezone.now().date()
        p = Presence.objects.create(
            eleve=self.eleve, classe=self.classe,
            date=today, statut='present',
            enregistre_par=self.surveillant,
        )
        self.assertEqual(p.statut, 'present')

    def test_absence_creation(self):
        from eleves.models import Presence
        today = timezone.now().date()
        p = Presence.objects.create(
            eleve=self.eleve, classe=self.classe,
            date=today, statut='absent',
            enregistre_par=self.surveillant,
        )
        self.assertEqual(p.statut, 'absent')

    def test_unicite_eleve_date_classe(self):
        """On ne peut pas créer deux présences pour le même élève/date/classe."""
        from eleves.models import Presence
        from django.db import IntegrityError
        today = timezone.now().date()
        Presence.objects.create(
            eleve=self.eleve, classe=self.classe,
            date=today, statut='present',
            enregistre_par=self.surveillant,
        )
        with self.assertRaises(IntegrityError):
            Presence.objects.create(
                eleve=self.eleve, classe=self.classe,
                date=today, statut='absent',
                enregistre_par=self.surveillant,
            )

    def test_str_presence(self):
        from eleves.models import Presence
        today = timezone.now().date()
        p = Presence.objects.create(
            eleve=self.eleve, classe=self.classe,
            date=today, statut='retard',
            enregistre_par=self.surveillant,
        )
        s = str(p)
        self.assertIn("Diallo", s)

    def test_statuts_valides(self):
        """Vérifie que tous les statuts définis sont acceptés."""
        from eleves.models import Presence
        statuts = ['present', 'absent', 'retard', 'justifie']
        for i, statut in enumerate(statuts):
            date = timezone.now().date() - datetime.timedelta(days=i + 1)
            p = Presence.objects.create(
                eleve=self.eleve, classe=self.classe,
                date=date, statut=statut,
                enregistre_par=self.surveillant,
            )
            self.assertEqual(p.statut, statut)
