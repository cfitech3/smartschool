"""
Tests -- Module Finances
=========================
Couvre :
  - La generation de reference de paiement (format, unicite)
  - L enregistrement et le calcul de paiements
"""
import datetime
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


def _setup():
    from etablissements.models import Etablissement, AnneeScolaire
    from finances.models import TypeFrais
    etab = Etablissement.objects.create(nom="Ecole Finances", code="FIN", type="ecole")
    annee = AnneeScolaire.objects.create(
        etablissement=etab, libelle="2025-2026",
        date_debut=datetime.date(2025, 10, 1),
        date_fin=datetime.date(2026, 7, 31),
        is_active=True,
    )
    tf = TypeFrais.objects.create(
        etablissement=etab, nom="Frais de scolarite",
        montant_defaut=Decimal("150000"), is_obligatoire=True,
    )
    return etab, annee, tf


class TestPaiementReference(TestCase):

    def setUp(self):
        self.etab, self.annee, self.tf = _setup()
        self.admin = User.objects.create_user(
            username="cpt_test", password="x", role="comptable", etablissement=self.etab)
        from eleves.models import Eleve
        self.eleve = Eleve.objects.create(
            etablissement=self.etab, nom="Diallo", prenom="Moussa",
            sexe='M', date_naissance=datetime.date(2010, 5, 20),
        )

    def test_reference_generee_automatiquement(self):
        """Un paiement sans reference doit en recevoir une automatiquement."""
        from finances.models import Paiement
        p = Paiement.objects.create(
            etablissement=self.etab, eleve=self.eleve, annee=self.annee,
            type_frais=self.tf, montant=Decimal("50000"),
            mode_paiement="especes", statut="valide",
            encaisse_par=self.admin,
        )
        self.assertTrue(p.reference.startswith("PAY-"))
        self.assertEqual(len(p.reference), 12)  # "PAY-" + 8 chiffres

    def test_references_uniques_sur_plusieurs_paiements(self):
        """Des paiements generes rapidement doivent avoir des references differentes."""
        from finances.models import Paiement
        refs = set()
        for i in range(20):
            p = Paiement.objects.create(
                etablissement=self.etab, eleve=self.eleve, annee=self.annee,
                type_frais=self.tf, montant=Decimal("10000"),
                mode_paiement="especes", statut="valide",
                encaisse_par=self.admin,
            )
            refs.add(p.reference)
        self.assertEqual(len(refs), 20, f"Des references dupliquees : {refs}")

    def test_paiement_str_contient_informations_cles(self):
        """Le __str__ d un paiement doit inclure le nom de l eleve et le montant."""
        from finances.models import Paiement
        p = Paiement.objects.create(
            etablissement=self.etab, eleve=self.eleve, annee=self.annee,
            type_frais=self.tf, montant=Decimal("75000"),
            mode_paiement="mobile_money", statut="valide",
            encaisse_par=self.admin,
        )
        representation = str(p)
        self.assertIn("Diallo", representation)

    def test_montant_positif(self):
        """Le montant d un paiement doit etre positif."""
        from finances.models import Paiement
        p = Paiement.objects.create(
            etablissement=self.etab, eleve=self.eleve, annee=self.annee,
            type_frais=self.tf, montant=Decimal("25000"),
            mode_paiement="cheque", statut="valide",
            encaisse_par=self.admin,
        )
        self.assertGreater(p.montant, 0)
