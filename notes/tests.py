"""
Tests -- Module Notes
======================
Couvre :
  - Le calcul de bulletin malien (NotePeriode.moyenne_finale, appreciation, moy_coeffic)
  - La fonction calculer_rangs_classe (correctness + O(n))
  - La fonction peut_modifier_note (securite d acces aux notes)
"""
import datetime
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


# ---- Helpers de fixture -----------------------------------------------------

def _setup_base(code="ETN"):
    """Cree un contexte complet : etablissement, annee, classe, periode, matieres."""
    from etablissements.models import (
        Etablissement, AnneeScolaire, Cycle, CycleActif, Niveau, Classe
    )
    from notes.models import Matiere, Periode

    etab = Etablissement.objects.create(nom=f"Ecole Tests {code}", code=code, type="ecole")
    annee = AnneeScolaire.objects.create(
        etablissement=etab, libelle="2025-2026",
        date_debut=datetime.date(2025, 10, 1),
        date_fin=datetime.date(2026, 7, 31),
        is_active=True,
    )
    cycle = Cycle.objects.create(
        etablissement=etab, type_cycle="premier_cycle",
        nom="1er Cycle", mode_calcul="compo",
        note_passage=Decimal("10"), note_max=Decimal("20"),
    )
    CycleActif.objects.create(etablissement=etab, cycle=cycle, is_active=True)
    niveau = Niveau.objects.create(etablissement=etab, cycle=cycle, nom="6eme", ordre=1)
    classe = Classe.objects.create(
        etablissement=etab, annee=annee, niveau=niveau, nom="6A", capacite_max=30
    )
    periode = Periode.objects.create(
        etablissement=etab, annee=annee, type="trimestre",
        numero=1, libelle="1er Trimestre",
        date_debut=datetime.date(2025, 10, 1),
        date_fin=datetime.date(2025, 12, 31),
        is_active=True,
    )
    mat_fr = Matiere.objects.create(etablissement=etab, nom="Francais", coefficient=3)
    mat_ma = Matiere.objects.create(etablissement=etab, nom="Mathematiques", coefficient=4)
    mat_cd = Matiere.objects.create(etablissement=etab, nom="Conduite", coefficient=1, is_conduite=True)
    return etab, annee, cycle, niveau, classe, periode, mat_fr, mat_ma, mat_cd


def _creer_eleve(etab, nom="Diallo", prenom="Moussa"):
    """Cree un eleve via Eleve.objects.create - laisse save() generer le matricule."""
    from eleves.models import Eleve
    return Eleve.objects.create(
        etablissement=etab, nom=nom, prenom=prenom,
        sexe='M', date_naissance=datetime.date(2012, 1, 1),
    )


def _inscrire(eleve, classe, annee):
    from eleves.models import Inscription
    return Inscription.objects.create(eleve=eleve, classe=classe, annee=annee, is_active=True)


def _creer_note(eleve, mat, classe, periode, saisi_par,
                moy_classe=None, moy_compo=None, note_conduite=None):
    from notes.models import NotePeriode
    return NotePeriode.objects.create(
        eleve=eleve, matiere=mat, classe=classe, periode=periode,
        moy_classe=moy_classe, moy_compo=moy_compo,
        note_max_classe=Decimal("20"), note_max_compo=Decimal("40"),
        note_conduite=note_conduite,
        saisi_par=saisi_par,
    )


# ---- Tests : NotePeriode.moyenne_finale -------------------------------------

class TestNotePeriodeMoyenneFinale(TestCase):

    def setUp(self):
        (self.etab, self.annee, self.cycle, self.niveau, self.classe,
         self.periode, self.mat_fr, self.mat_ma, self.mat_cd) = _setup_base("ETN1")
        self.admin = User.objects.create_user(username="adm_notes", password="x", role="admin")
        self.eleve = _creer_eleve(self.etab, "Diarra", "Sekou")
        _inscrire(self.eleve, self.classe, self.annee)

    def test_moyenne_finale_deux_colonnes(self):
        """Formule : moy_classe/20*20 = moy_classe ; moy_compo/40*20 = moy_compo/2. Moy = (A+B)/2"""
        note = _creer_note(self.eleve, self.mat_fr, self.classe, self.periode,
                           self.admin, moy_classe=Decimal("14"), moy_compo=Decimal("28"))
        # moy_classe normalise = 14 ; moy_compo normalise = 28/40*20 = 14 ; moy = 14
        self.assertAlmostEqual(float(note.moyenne_finale), 14.0, places=1)

    def test_moyenne_finale_classe_seule(self):
        """Si moy_compo absente, la moyenne = moy_classe directement."""
        note = _creer_note(self.eleve, self.mat_fr, self.classe, self.periode,
                           self.admin, moy_classe=Decimal("16"), moy_compo=None)
        self.assertAlmostEqual(float(note.moyenne_finale), 16.0, places=1)

    def test_moyenne_finale_conduite(self):
        """Pour conduite, la moyenne = note_conduite directement."""
        note = _creer_note(self.eleve, self.mat_cd, self.classe, self.periode,
                           self.admin, note_conduite=Decimal("18"))
        self.assertAlmostEqual(float(note.moyenne_finale), 18.0, places=1)

    def test_moyenne_none_si_aucune_note(self):
        note = _creer_note(self.eleve, self.mat_fr, self.classe, self.periode,
                           self.admin, moy_classe=None, moy_compo=None)
        self.assertIsNone(note.moyenne_finale)

    def test_moy_coeffic(self):
        """moy_coeffic = moyenne_finale * coefficient."""
        note = _creer_note(self.eleve, self.mat_fr, self.classe, self.periode,
                           self.admin, moy_classe=Decimal("14"), moy_compo=Decimal("28"))
        # moyenne_finale = 14.0, coeff mat_fr = 3 → moy_coeffic = 42.0
        self.assertAlmostEqual(float(note.moy_coeffic), 42.0, places=1)


# ---- Tests : calculer_rangs_classe (O(n)) -----------------------------------

class TestCalculerRangsClasse(TestCase):

    def setUp(self):
        (self.etab, self.annee, self.cycle, self.niveau, self.classe,
         self.periode, self.mat_fr, self.mat_ma, self.mat_cd) = _setup_base("RNG1")
        self.admin = User.objects.create_user(username="adm_rg", password="x", role="admin")

    def _inscrit_note(self, nom, prenom, mc_fr, mn_fr):
        eleve = _creer_eleve(self.etab, nom, prenom)
        _inscrire(eleve, self.classe, self.annee)
        _creer_note(eleve, self.mat_fr, self.classe, self.periode,
                    self.admin, moy_classe=Decimal(str(mc_fr)), moy_compo=Decimal(str(mn_fr)))
        return eleve

    def test_rangs_corrects_trois_eleves(self):
        from notes.views_notes import calculer_rangs_classe
        e1 = self._inscrit_note("Alpha", "Un", 18, 36)   # moy max → rang 1
        e2 = self._inscrit_note("Beta", "Deux", 12, 24)  # moy moy → rang 2
        e3 = self._inscrit_note("Gamma", "Trois", 8, 16) # moy min → rang 3

        rangs = calculer_rangs_classe(self.classe, self.periode, [self.mat_fr])

        self.assertEqual(rangs.get(e1.pk), 1, "Alpha devrait etre 1er")
        self.assertEqual(rangs.get(e2.pk), 2, "Beta devrait etre 2eme")
        self.assertEqual(rangs.get(e3.pk), 3, "Gamma devrait etre 3eme")

    def test_eleve_sans_note_absent_du_classement(self):
        from notes.views_notes import calculer_rangs_classe
        e_avec = self._inscrit_note("Avec", "Note", 14, 28)
        e_sans = _creer_eleve(self.etab, "Sans", "Note")
        _inscrire(e_sans, self.classe, self.annee)

        rangs = calculer_rangs_classe(self.classe, self.periode, [self.mat_fr])
        self.assertIn(e_avec.pk, rangs)
        self.assertNotIn(e_sans.pk, rangs)

    def test_vide_si_aucune_note(self):
        from notes.views_notes import calculer_rangs_classe
        eleve = _creer_eleve(self.etab, "Personne", "Zero")
        _inscrire(eleve, self.classe, self.annee)
        rangs = calculer_rangs_classe(self.classe, self.periode, [self.mat_fr])
        self.assertEqual(rangs, {})

    def test_retourne_un_dict(self):
        from notes.views_notes import calculer_rangs_classe
        rangs = calculer_rangs_classe(self.classe, self.periode, [self.mat_fr])
        self.assertIsInstance(rangs, dict)


# ---- Tests : peut_modifier_note (securite) ----------------------------------

class TestPeutModifierNote(TestCase):

    def setUp(self):
        (self.etab, self.annee, self.cycle, self.niveau, self.classe,
         self.periode, self.mat_fr, self.mat_ma, self.mat_cd) = _setup_base("SEC1")
        self.admin = User.objects.create_user(
            username="adm_pm", password="x", role="admin", etablissement=self.etab)
        self.surveillant = User.objects.create_user(
            username="surv_pm", password="x", role="surveillant", etablissement=self.etab)
        self.eleve = _creer_eleve(self.etab, "TestPerm", "Eleve")
        _inscrire(self.eleve, self.classe, self.annee)

    def _note_fr(self):
        return _creer_note(self.eleve, self.mat_fr, self.classe,
                           self.periode, self.admin, moy_classe=Decimal("12"))

    def _note_conduite(self):
        return _creer_note(self.eleve, self.mat_cd, self.classe,
                           self.periode, self.admin, note_conduite=Decimal("15"))

    def test_admin_peut_toujours_modifier(self):
        from notes.views_notes import peut_modifier_note
        ok, _ = peut_modifier_note(self.admin, self._note_fr())
        self.assertTrue(ok)

    def test_surveillant_peut_modifier_conduite(self):
        from notes.views_notes import peut_modifier_note
        ok, _ = peut_modifier_note(self.surveillant, self._note_conduite())
        self.assertTrue(ok, "Le surveillant doit pouvoir modifier la conduite")

    def test_surveillant_ne_peut_pas_modifier_matiere_normale(self):
        from notes.views_notes import peut_modifier_note
        ok, msg = peut_modifier_note(self.surveillant, self._note_fr())
        self.assertFalse(ok)
        self.assertIn("conduite", msg.lower())
