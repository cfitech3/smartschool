from django.db import models, transaction
from django.utils import timezone
from django.core.validators import MinValueValidator
import secrets

class TypeFrais(models.Model):
    PERIODICITES = [('unique', 'Paiement Unique'), ('mensuel', 'Mensuel'), ('tranches', 'Par Tranches')]
    etablissement = models.ForeignKey('etablissements.Etablissement', on_delete=models.CASCADE)
    annee = models.ForeignKey(
        'etablissements.AnneeScolaire', on_delete=models.CASCADE, null=True, blank=True,
        help_text="Année scolaire concernée. Si vide, s'applique à toutes les années (legacy)."
    )
    nom = models.CharField(max_length=100)
    montant_defaut = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    is_obligatoire = models.BooleanField(default=True)
    periodicite = models.CharField(max_length=20, choices=PERIODICITES, default='unique')
    nombre_tranches = models.IntegerField(default=1, blank=True, help_text="Si périodicité par tranches, combien de tranches ?")
    description = models.TextField(blank=True)

    def __str__(self):
        if self.annee:
            return f"{self.nom} ({self.annee.libelle})"
        return self.nom


class ReductionFrais(models.Model):
    """
    Bourse / remise accordée à un élève sur un type de frais.
    Le champ `montant` contient TOUJOURS le montant effectif déduit (FCFA),
    même en mode pourcentage : il est recalculé dans save() à partir du tarif
    standard du TypeFrais. Le tarif de la classe n'est jamais modifié.
    """
    CATEGORIES = [
        ('bourse_etat',       "Bourse d'État / Nationale"),
        ('bourse_excellence', "Bourse d'excellence / Mérite"),
        ('demi_bourse',       "Demi-bourse"),
        ('fratrie',           "Réduction Fratrie / Famille nombreuse"),
        ('personnel',         "Enfant du personnel"),
        ('prise_en_charge',   "Prise en charge par un tiers (ONG, entreprise...)"),
        ('social',            "Cas social / Dérogation Direction"),
        ('autre',             "Autre réduction"),
    ]
    MODES_CALCUL = [('fixe', 'Montant fixe (FCFA)'), ('pourcentage', 'Pourcentage (%)')]

    etablissement = models.ForeignKey('etablissements.Etablissement', on_delete=models.CASCADE)
    eleve = models.ForeignKey('eleves.Eleve', on_delete=models.CASCADE, related_name='reductions')
    annee = models.ForeignKey('etablissements.AnneeScolaire', on_delete=models.CASCADE)
    type_frais = models.ForeignKey(TypeFrais, on_delete=models.CASCADE)
    categorie = models.CharField(max_length=30, choices=CATEGORIES, default='autre')
    mode_calcul = models.CharField(max_length=15, choices=MODES_CALCUL, default='fixe')
    valeur_pourcentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
        help_text="Pourcentage de remise (0 à 100) si mode = pourcentage."
    )
    montant = models.DecimalField(max_digits=12, decimal_places=0, default=0, help_text="Montant effectif réduit (FCFA).")
    organisme_tiers = models.CharField(max_length=150, blank=True, help_text="Organisme payeur (État, ONG, Mairie, Entreprise...)")
    motif = models.CharField(max_length=200, blank=True)
    date_accord = models.DateTimeField(default=timezone.now)
    accordee_par = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='reductions_accordees')

    class Meta:
        unique_together = ['eleve', 'annee', 'type_frais']

    def __str__(self): return f"Réduction de {self.montant} FCFA pour {self.eleve}"

    def calculer_montant(self):
        """Montant effectif (FCFA) borné entre 0 et le tarif standard du frais."""
        from decimal import Decimal, ROUND_HALF_UP
        base = Decimal(str(self.type_frais.montant_defaut or 0))
        if self.mode_calcul == 'pourcentage':
            pct = Decimal(str(self.valeur_pourcentage or 0))
            pct = max(Decimal('0'), min(Decimal('100'), pct))
            val = (base * pct / Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        else:
            val = Decimal(str(self.montant or 0))
        return max(Decimal('0'), min(base, val)) if base > 0 else max(Decimal('0'), val)

    def save(self, *args, **kwargs):
        self.montant = self.calculer_montant()
        super().save(*args, **kwargs)

    @property
    def est_exoneration_totale(self):
        return self.type_frais.montant_defaut > 0 and self.montant >= self.type_frais.montant_defaut

    @property
    def libelle_valeur(self):
        if self.mode_calcul == 'pourcentage' and self.valeur_pourcentage is not None:
            return f"-{self.valeur_pourcentage.normalize():f} %"
        return f"-{int(self.montant):,} F".replace(',', ' ')


class Paiement(models.Model):
    MODES = [('especes','Especes'),('mobile_money','Mobile Money'),('virement','Virement')]
    STATUTS = [('valide','Valide'),('annule','Annule'),('attente','En attente')]

    etablissement = models.ForeignKey('etablissements.Etablissement', on_delete=models.CASCADE)
    eleve = models.ForeignKey('eleves.Eleve', on_delete=models.CASCADE, related_name='paiements')
    annee = models.ForeignKey('etablissements.AnneeScolaire', on_delete=models.CASCADE)
    type_frais = models.ForeignKey(TypeFrais, on_delete=models.CASCADE)
    montant = models.DecimalField(
        max_digits=12, decimal_places=0,
        validators=[MinValueValidator(1, message="Le montant doit être strictement positif.")]
    )
    mode_paiement = models.CharField(max_length=20, choices=MODES, default='especes')
    statut = models.CharField(max_length=20, choices=STATUTS, default='valide', db_index=True)
    reference = models.CharField(max_length=50, unique=True, blank=True)
    periode_payee = models.CharField(max_length=50, blank=True, help_text="Mois ou Tranche réglée (ex: Novembre, Tranche 1)")
    date_paiement = models.DateTimeField(default=timezone.now, db_index=True)
    encaisse_par = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, related_name="encaissements")
    notes = models.TextField(blank=True)
    
    # P3.9 : Traçabilité des annulations
    date_annulation = models.DateTimeField(null=True, blank=True)
    motif_annulation = models.CharField(max_length=255, blank=True)
    annule_par = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name="annulations")

    class Meta:
        ordering = ['-date_paiement']

    def __str__(self): return f"{self.eleve.nom_complet} — {self.montant} FCFA"

    @staticmethod
    def _generer_reference_atomique(etablissement_id=None):
        """
        Génère une référence de paiement unique et non-devinable (PAY-XXXXXXXX)
        via CSPRNG (secrets.randbelow) sans contention de verrou inter-établissements
        ni scan COUNT(*).
        """
        for _ in range(20):
            reference = f"PAY-{secrets.randbelow(100_000_000):08d}"
            if not Paiement.objects.filter(reference=reference).exists():
                return reference
        raise RuntimeError("Impossible de générer une référence de paiement unique.")

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self._generer_reference_atomique(etablissement_id=self.etablissement_id)
        super().save(*args, **kwargs)


class Echeance(models.Model):
    """Représente une tranche de paiement due par un élève."""
    STATUTS = [
        ('a_payer',  'À payer'),
        ('payee',    'Payée'),
        ('retard',   'En retard'),
        ('dispensee','Dispensée'),
    ]
    etablissement = models.ForeignKey('etablissements.Etablissement', on_delete=models.CASCADE)
    eleve         = models.ForeignKey('eleves.Eleve', on_delete=models.CASCADE, related_name='echeances')
    annee         = models.ForeignKey('etablissements.AnneeScolaire', on_delete=models.CASCADE)
    type_frais    = models.ForeignKey(TypeFrais, on_delete=models.CASCADE, related_name='echeances')
    numero        = models.PositiveSmallIntegerField(help_text="Numéro de la tranche (1, 2, 3...)")
    libelle       = models.CharField(max_length=50, help_text="Ex: Tranche 1")
    montant       = models.DecimalField(max_digits=12, decimal_places=0)
    date_limite   = models.DateField(null=True, blank=True)
    statut        = models.CharField(max_length=12, choices=STATUTS, default='a_payer', db_index=True)
    paiement      = models.ForeignKey(Paiement, on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name='echeances_liees')
    date_paiement = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['eleve','numero']
        unique_together = ['eleve', 'annee', 'type_frais', 'numero']

    def __str__(self):
        return f"{self.eleve.nom_complet} — {self.libelle} ({self.type_frais.nom}) — {self.get_statut_display()}"

    @property
    def est_en_retard(self):
        from django.utils import timezone
        return (self.statut == 'a_payer' and self.date_limite
                and self.date_limite < timezone.now().date())

    def marquer_payee(self, paiement):
        from django.utils import timezone
        self.statut = 'payee'
        self.paiement = paiement
        self.date_paiement = timezone.now()
        self.save()
