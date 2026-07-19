"""
Tests — Module Finances (enrichi)
==================================
Couvre :
  - Génération de références de paiement (format, unicité)
  - TypeFrais (création, obligatoire, periodicite)
  - Paiement (création, statuts, modes, annulation, tracabilité)
  - Echeance (création, statut retard, marquer_payee, est_en_retard)
  - ReductionFrais (unicité eleve/annee/type)
"""
import datetime
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


# ── Helpers de fixture ────────────────────────────────────────────────────────

def _setup_base(code="FIN"):
    from etablissements.models import Etablissement, AnneeScolaire
    from finances.models import TypeFrais
    etab = Etablissement.objects.create(nom=f"Ecole {code}", code=code, type="ecole")
    annee = AnneeScolaire.objects.create(
        etablissement=etab, libelle="2025-2026",
        date_debut=datetime.date(2025, 10, 1),
        date_fin=datetime.date(2026, 7, 31),
        is_active=True,
    )
    tf = TypeFrais.objects.create(
        etablissement=etab, nom="Frais de scolarite",
        montant_defaut=Decimal("150000"), is_obligatoire=True,
        periodicite="unique",
    )
    return etab, annee, tf


def _creer_admin(etab, username="admin_fin"):
    return User.objects.create_user(
        username=username, password="x", role="comptable", etablissement=etab
    )


def _creer_eleve(etab, nom="Diallo", prenom="Moussa"):
    from eleves.models import Eleve
    return Eleve.objects.create(
        etablissement=etab, nom=nom, prenom=prenom,
        sexe='M', date_naissance=datetime.date(2010, 5, 20),
    )


def _creer_paiement(etab, annee, tf, eleve, user, montant=50000, statut='valide'):
    from finances.models import Paiement
    return Paiement.objects.create(
        etablissement=etab, eleve=eleve, annee=annee,
        type_frais=tf, montant=Decimal(str(montant)),
        mode_paiement="especes", statut=statut,
        encaisse_par=user,
    )


# ── Tests : Référence de paiement ─────────────────────────────────────────────

class TestPaiementReference(TestCase):

    def setUp(self):
        self.etab, self.annee, self.tf = _setup_base("REF")
        self.admin = _creer_admin(self.etab, "cpt_ref")
        self.eleve = _creer_eleve(self.etab)

    def test_reference_generee_automatiquement(self):
        """Un paiement sans reference doit en recevoir une automatiquement."""
        p = _creer_paiement(self.etab, self.annee, self.tf, self.eleve, self.admin)
        self.assertTrue(p.reference.startswith("PAY-"))
        self.assertEqual(len(p.reference), 12)  # "PAY-" + 8 chiffres

    def test_references_uniques_sur_plusieurs_paiements(self):
        """Des paiements générés rapidement doivent avoir des références différentes."""
        refs = set()
        for i in range(20):
            p = _creer_paiement(self.etab, self.annee, self.tf, self.eleve, self.admin)
            refs.add(p.reference)
        self.assertEqual(len(refs), 20, f"Références dupliquées : {refs}")

    def test_paiement_str_contient_informations_cles(self):
        p = _creer_paiement(self.etab, self.annee, self.tf, self.eleve, self.admin,
                             montant=75000)
        self.assertIn("Diallo", str(p))

    def test_montant_positif(self):
        p = _creer_paiement(self.etab, self.annee, self.tf, self.eleve, self.admin,
                             montant=25000)
        self.assertGreater(p.montant, 0)


# ── Tests : TypeFrais ─────────────────────────────────────────────────────────

class TestTypeFrais(TestCase):

    def setUp(self):
        self.etab, self.annee, _ = _setup_base("TF")

    def test_creation_type_frais(self):
        from finances.models import TypeFrais
        tf = TypeFrais.objects.create(
            etablissement=self.etab, nom="Frais d'inscription",
            montant_defaut=Decimal("25000"), is_obligatoire=True,
        )
        self.assertEqual(tf.nom, "Frais d'inscription")
        self.assertTrue(tf.is_obligatoire)

    def test_periodicite_par_tranches(self):
        from finances.models import TypeFrais
        tf = TypeFrais.objects.create(
            etablissement=self.etab, nom="Mensualité",
            montant_defaut=Decimal("10000"),
            periodicite="tranches", nombre_tranches=10,
        )
        self.assertEqual(tf.periodicite, "tranches")
        self.assertEqual(tf.nombre_tranches, 10)

    def test_str_avec_annee(self):
        from finances.models import TypeFrais
        tf = TypeFrais.objects.create(
            etablissement=self.etab, nom="Scolarité",
            montant_defaut=Decimal("100000"),
            annee=self.annee,
        )
        s = str(tf)
        self.assertIn("Scolarité", s)
        self.assertIn("2025-2026", s)


# ── Tests : Paiement statuts et annulation ────────────────────────────────────

class TestPaiementStatuts(TestCase):

    def setUp(self):
        self.etab, self.annee, self.tf = _setup_base("STA")
        self.admin = _creer_admin(self.etab, "cpt_sta")
        self.eleve = _creer_eleve(self.etab)

    def test_paiement_valide_par_defaut(self):
        p = _creer_paiement(self.etab, self.annee, self.tf, self.eleve, self.admin)
        self.assertEqual(p.statut, 'valide')

    def test_paiement_en_attente(self):
        p = _creer_paiement(self.etab, self.annee, self.tf, self.eleve, self.admin,
                             statut='attente')
        self.assertEqual(p.statut, 'attente')

    def test_annulation_traceabilite(self):
        """L'annulation doit enregistrer la date, le motif et le responsable."""
        p = _creer_paiement(self.etab, self.annee, self.tf, self.eleve, self.admin)
        p.statut = 'annule'
        p.date_annulation = timezone.now()
        p.motif_annulation = "Erreur de saisie"
        p.annule_par = self.admin
        p.save()

        p.refresh_from_db()
        self.assertEqual(p.statut, 'annule')
        self.assertIsNotNone(p.date_annulation)
        self.assertEqual(p.motif_annulation, "Erreur de saisie")
        self.assertEqual(p.annule_par, self.admin)

    def test_modes_paiement(self):
        """Tous les modes de paiement définis doivent être acceptés."""
        modes = ['especes', 'mobile_money', 'virement']
        for mode in modes:
            p = _creer_paiement(self.etab, self.annee, self.tf, self.eleve, self.admin)
            p.mode_paiement = mode
            p.save()
            p.refresh_from_db()
            self.assertEqual(p.mode_paiement, mode)

    def test_validateur_montant_positif(self):
        """Un montant négatif ou nul doit lever une ValidationError."""
        from finances.models import Paiement
        from django.core.exceptions import ValidationError
        p = Paiement(
            etablissement=self.etab, eleve=self.eleve, annee=self.annee,
            type_frais=self.tf, montant=Decimal("0"),
            encaisse_par=self.admin,
        )
        with self.assertRaises(ValidationError):
            p.full_clean()


# ── Tests : Echeance ──────────────────────────────────────────────────────────

class TestEcheance(TestCase):

    def setUp(self):
        self.etab, self.annee, self.tf = _setup_base("ECH")
        self.admin = _creer_admin(self.etab, "cpt_ech")
        self.eleve = _creer_eleve(self.etab)

    def _creer_echeance(self, numero=1, statut='a_payer', date_limite=None):
        from finances.models import Echeance
        return Echeance.objects.create(
            etablissement=self.etab, eleve=self.eleve,
            annee=self.annee, type_frais=self.tf,
            numero=numero, libelle=f"Tranche {numero}",
            montant=Decimal("50000"), statut=statut,
            date_limite=date_limite,
        )

    def test_echeance_creation(self):
        e = self._creer_echeance()
        self.assertEqual(e.statut, 'a_payer')
        self.assertEqual(e.numero, 1)

    def test_est_en_retard_true(self):
        """Une échéance a_payer dont la date_limite est passée doit être en retard."""
        hier = datetime.date.today() - datetime.timedelta(days=1)
        e = self._creer_echeance(date_limite=hier)
        self.assertTrue(e.est_en_retard)

    def test_est_en_retard_false_si_payee(self):
        """Une échéance payée ne doit pas être en retard même si la date est passée."""
        hier = datetime.date.today() - datetime.timedelta(days=1)
        e = self._creer_echeance(statut='payee', date_limite=hier)
        self.assertFalse(e.est_en_retard)

    def test_est_en_retard_false_si_future(self):
        """Une échéance avec date_limite future n'est pas en retard."""
        demain = datetime.date.today() + datetime.timedelta(days=1)
        e = self._creer_echeance(date_limite=demain)
        self.assertFalse(e.est_en_retard)

    def test_marquer_payee(self):
        """marquer_payee doit mettre le statut à 'payee' et lier le paiement."""
        e = self._creer_echeance()
        p = _creer_paiement(self.etab, self.annee, self.tf, self.eleve, self.admin)
        e.marquer_payee(p)
        e.refresh_from_db()
        self.assertEqual(e.statut, 'payee')
        self.assertEqual(e.paiement, p)
        self.assertIsNotNone(e.date_paiement)

    def test_uniquete_eleve_annee_type_numero(self):
        """L'unicité (eleve, annee, type_frais, numero) doit être respectée."""
        from django.db import IntegrityError
        self._creer_echeance(numero=1)
        with self.assertRaises(IntegrityError):
            self._creer_echeance(numero=1)

    def test_str_echeance(self):
        e = self._creer_echeance()
        s = str(e)
        self.assertIn("Diallo", s)
        self.assertIn("Tranche 1", s)


# ── Tests : ReductionFrais ────────────────────────────────────────────────────

class TestReductionFrais(TestCase):

    def setUp(self):
        self.etab, self.annee, self.tf = _setup_base("RED")
        self.eleve = _creer_eleve(self.etab)

    def test_creation_reduction(self):
        from finances.models import ReductionFrais
        r = ReductionFrais.objects.create(
            etablissement=self.etab, eleve=self.eleve,
            annee=self.annee, type_frais=self.tf,
            montant=Decimal("30000"), motif="Bourse",
        )
        self.assertEqual(r.motif, "Bourse")
        self.assertEqual(r.montant, Decimal("30000"))

    def test_unicite_eleve_annee_type(self):
        """Un élève ne peut avoir qu'une réduction par type de frais et par année."""
        from finances.models import ReductionFrais
        from django.db import IntegrityError
        ReductionFrais.objects.create(
            etablissement=self.etab, eleve=self.eleve,
            annee=self.annee, type_frais=self.tf,
            montant=Decimal("20000"),
        )
        with self.assertRaises(IntegrityError):
            ReductionFrais.objects.create(
                etablissement=self.etab, eleve=self.eleve,
                annee=self.annee, type_frais=self.tf,
                montant=Decimal("10000"),
            )
