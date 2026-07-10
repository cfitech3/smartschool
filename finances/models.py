from django.db import models
from django.utils import timezone
import random, string

class TypeFrais(models.Model):
    etablissement = models.ForeignKey('etablissements.Etablissement', on_delete=models.CASCADE)
    nom = models.CharField(max_length=100)
    montant_defaut = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    is_obligatoire = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    def __str__(self): return self.nom


class Paiement(models.Model):
    MODES = [('especes','Especes'),('mobile_money','Mobile Money'),('virement','Virement')]
    STATUTS = [('valide','Valide'),('annule','Annule'),('attente','En attente')]

    etablissement = models.ForeignKey('etablissements.Etablissement', on_delete=models.CASCADE)
    eleve = models.ForeignKey('eleves.Eleve', on_delete=models.CASCADE, related_name='paiements')
    annee = models.ForeignKey('etablissements.AnneeScolaire', on_delete=models.CASCADE)
    type_frais = models.ForeignKey(TypeFrais, on_delete=models.CASCADE)
    montant = models.DecimalField(max_digits=12, decimal_places=0)
    mode_paiement = models.CharField(max_length=20, choices=MODES, default='especes')
    statut = models.CharField(max_length=20, choices=STATUTS, default='valide')
    reference = models.CharField(max_length=50, unique=True, blank=True)
    date_paiement = models.DateTimeField(default=timezone.now)
    encaisse_par = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-date_paiement']

    def __str__(self): return f"{self.eleve.nom_complet} — {self.montant} FCFA"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = 'PAY-' + ''.join(random.choices(string.digits, k=8))
        super().save(*args, **kwargs)
