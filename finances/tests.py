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


class TestAnnulationPaiementPartielEcheance(TestCase):
    """Régression P0 : annuler un paiement partiel antérieur doit resynchroniser l'échéance."""

    def setUp(self):
        from django.urls import reverse
        self.reverse = reverse
        self.etab, self.annee, self.tf = _setup_base("PART")
        self.comptable = _creer_admin(self.etab, "cpt_part")
        self.eleve = _creer_eleve(self.etab)

    def test_annulation_premier_paiement_partiel_remet_echeance_a_payer(self):
        from finances.models import Echeance, Paiement
        ech = Echeance.objects.create(
            etablissement=self.etab, eleve=self.eleve,
            annee=self.annee, type_frais=self.tf,
            numero=1, libelle="Tranche 1", montant=Decimal("50000"),
            statut="a_payer",
        )
        self.client.force_login(self.comptable)

        # Deux paiements partiels de 25 000 F chacun
        for _ in range(2):
            resp = self.client.post(self.reverse("enregistrer_paiement"), {
                "eleve": self.eleve.pk,
                "type_frais": self.tf.pk,
                "montant": "25000",
                "mode_paiement": "especes",
                "periode_payee": "",
            })
            self.assertEqual(resp.status_code, 302)

        ech.refresh_from_db()
        self.assertEqual(ech.statut, "payee")

        # Annuler le PREMIER paiement (celui auquel ech.paiement ne pointe pas)
        premier_paiement = Paiement.objects.filter(eleve=self.eleve).order_by("pk").first()
        resp = self.client.post(self.reverse("annuler_paiement", kwargs={"pk": premier_paiement.pk}), {
            "motif_annulation": "Double saisie",
        })
        self.assertEqual(resp.status_code, 302)

        ech.refresh_from_db()
        self.assertEqual(ech.statut, "a_payer")
        self.assertIsNone(ech.paiement)


class TestBourseApresAcomptePartiel(TestCase):
    """Régression Section 2 : l'octroi d'une bourse après un acompte partiel ne doit pas ignorer l'acompte."""

    def setUp(self):
        self.etab, self.annee, self.tf = _setup_base("ACMP")
        self.comptable = _creer_admin(self.etab, "cpt_acmp")
        self.eleve = _creer_eleve(self.etab)

    def test_recalcul_echeances_consolide_acompte_partiel(self):
        from finances.models import Echeance, ReductionFrais
        from finances.services_bourses import recalculer_echeances_eleve, resume_echeancier

        for num in (1, 2, 3):
            Echeance.objects.create(
                etablissement=self.etab, eleve=self.eleve,
                annee=self.annee, type_frais=self.tf,
                numero=num, libelle=f"Tranche {num}", montant=Decimal("50000"),
                statut="a_payer",
            )

        # Acompte partiel de 30 000 F (< 50 000 F, donc aucune tranche initiale n'est 'payee')
        _creer_paiement(self.etab, self.annee, self.tf, self.eleve, self.comptable, montant=30000)

        # Bourse de 30 000 F -> net = 120 000 F, déjà payé = 30 000 F -> reste = 90 000 F
        ReductionFrais.objects.create(
            etablissement=self.etab, eleve=self.eleve,
            annee=self.annee, type_frais=self.tf,
            montant=Decimal("30000"), motif="Bourse mérite",
        )
        recalculer_echeances_eleve(self.eleve, self.annee, self.tf)

        echeances, paye, reste, net = resume_echeancier(self.eleve, self.annee, self.tf)
        self.assertEqual(net, Decimal("120000"))
        self.assertEqual(paye, Decimal("30000"))
        self.assertEqual(reste, Decimal("90000"))
        somme_ouvertes = sum(Decimal(str(e.montant)) for e in echeances if e.statut != "payee")
        somme_payees = sum(Decimal(str(e.montant)) for e in echeances if e.statut == "payee")
        self.assertEqual(somme_payees, Decimal("30000"))
        self.assertEqual(somme_ouvertes, Decimal("90000"))


class TestInvariantsComptables95(TestCase):
    """Tests des 5 chantiers Intégrité Financière & Métier (Objectif 9.5/10)."""

    def setUp(self):
        from django.core.cache import cache
        from django.urls import reverse
        cache.clear()
        self.reverse = reverse
        self.etab, self.annee, self.tf = _setup_base("INV95")
        self.comptable = _creer_admin(self.etab, "cpt_inv95")
        self.eleve = _creer_eleve(self.etab, nom="Keita", prenom="Salif")

    def test_immutabilite_montant_et_blocage_suppression_paiement(self):
        from django.core.exceptions import ValidationError
        p = _creer_paiement(self.etab, self.annee, self.tf, self.eleve, self.comptable, montant=50000)

        p.montant = Decimal("10000")
        with self.assertRaises(ValidationError):
            p.save()

        p.refresh_from_db()
        self.assertEqual(p.montant, Decimal("50000"))

        with self.assertRaises(ValidationError):
            p.delete()

    def test_anti_surpaiement_et_boursier_100_pourcent(self):
        from finances.models import Paiement, ReductionFrais
        self.client.force_login(self.comptable)

        # Surpaiement > 150 000 F refusé
        resp = self.client.post(self.reverse("enregistrer_paiement"), {
            "eleve": self.eleve.pk, "type_frais": self.tf.pk,
            "montant": "200000", "mode_paiement": "especes",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Paiement.objects.filter(eleve=self.eleve).count(), 0)

        # Bourse 100 % -> encaissement bloqué (reste = 0)
        ReductionFrais.objects.create(
            etablissement=self.etab, eleve=self.eleve, annee=self.annee,
            type_frais=self.tf, mode_calcul="pourcentage", valeur_pourcentage=Decimal("100"),
        )
        resp2 = self.client.post(self.reverse("enregistrer_paiement"), {
            "eleve": self.eleve.pk, "type_frais": self.tf.pk,
            "montant": "10000", "mode_paiement": "especes",
        })
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(Paiement.objects.filter(eleve=self.eleve).count(), 0)

    def test_idempotence_anti_double_clic_caisse(self):
        from finances.models import Paiement
        self.client.force_login(self.comptable)
        get_resp = self.client.get(self.reverse("enregistrer_paiement"))
        token = get_resp.context["idempotency_token"]

        payload = {
            "eleve": self.eleve.pk, "type_frais": self.tf.pk,
            "montant": "50000", "mode_paiement": "especes",
            "idempotency_token": token,
        }
        r1 = self.client.post(self.reverse("enregistrer_paiement"), payload)
        r2 = self.client.post(self.reverse("enregistrer_paiement"), payload)
        self.assertEqual(r1.status_code, 302)
        self.assertEqual(r2.status_code, 302)
        self.assertEqual(Paiement.objects.filter(eleve=self.eleve, statut="valide").count(), 1)

    def test_qr_recu_detecte_paiement_annule_apres_impression(self):
        from core.verification_qr import generer_token_document
        p = _creer_paiement(self.etab, self.annee, self.tf, self.eleve, self.comptable, montant=50000)
        token = generer_token_document(
            "recu", self.eleve, annee=self.annee,
            extra={"pay_pk": p.pk, "ref": p.reference, "mnt": int(p.montant)},
        )

        # Tant que le paiement est valide -> QR valide (200)
        url_verif = self.reverse("verifier_document_qr", kwargs={"token": token})
        resp_ok = self.client.get(url_verif)
        self.assertEqual(resp_ok.status_code, 200)
        self.assertTrue(resp_ok.context["valide"])

        # Une fois le paiement annulé en caisse -> le même QR papier renvoie 400 + valide=False !
        self.client.force_login(self.comptable)
        self.client.post(self.reverse("annuler_paiement", kwargs={"pk": p.pk}), {
            "motif_annulation": "Chèque sans provision",
        })
        resp_fraud = self.client.get(url_verif)
        self.assertEqual(resp_fraud.status_code, 400)
        self.assertFalse(resp_fraud.context["valide"])
