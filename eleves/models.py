from django.db import models, transaction
from django.utils import timezone


class Eleve(models.Model):
    SEXES = [('M','Masculin'),('F','Feminin')]
    etablissement = models.ForeignKey('etablissements.Etablissement', on_delete=models.CASCADE, related_name='eleves')
    matricule = models.CharField(max_length=30, unique=True, blank=True)
    photo = models.ImageField(upload_to='eleves/photos/', blank=True, null=True)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    sexe = models.CharField(max_length=1, choices=SEXES)
    date_naissance = models.DateField()
    lieu_naissance = models.CharField(max_length=100, blank=True)
    adresse = models.TextField(blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    tuteur = models.ForeignKey('Tuteur', on_delete=models.SET_NULL, null=True, blank=True, related_name='eleves')
    user_compte = models.OneToOneField('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='profil_eleve', help_text="Compte de connexion de l'eleve (optionnel)")
    date_inscription = models.DateField(default=timezone.now)
    is_active = models.BooleanField(default=True, db_index=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nom','prenom']

    def __str__(self): return f"{self.nom} {self.prenom} ({self.matricule})"

    @staticmethod
    def _generer_matricule_atomique(etablissement, annee_str):
        """
        Génère un matricule unique de façon atomique en utilisant un compteur
        séquentiel basé sur les matricules existants.

        Format : CODE_ETAB-ANNEE-XXXX (XXXX = numéro séquentiel à 4 chiffres)

        L'utilisation de select_for_update() sur la requête COUNT garantit qu'en
        cas d'inscriptions simultanées, chaque worker obtient un numéro différent
        sans collision, même sous forte charge.
        """
        prefixe = f"{etablissement.code}-{annee_str}-"
        with transaction.atomic():
            # Compter les élèves existants avec ce préfixe pour déterminer
            # le prochain numéro séquentiel. select_for_update() verrouille
            # les lignes concernées pendant la transaction.
            nb_existants = (
                Eleve.objects
                .select_for_update()
                .filter(matricule__startswith=prefixe)
                .count()
            )
            numero = nb_existants + 1
            matricule = f"{prefixe}{numero:04d}"
            # Vérification de sécurité : si par hasard ce matricule existe
            # déjà (migration de données), incrémenter jusqu'à trouver un libre.
            while Eleve.objects.filter(matricule=matricule).exists():
                numero += 1
                matricule = f"{prefixe}{numero:04d}"
            return matricule

    def save(self, *args, **kwargs):
        if not self.matricule:
            from etablissements.models import AnneeScolaire
            annee = AnneeScolaire.objects.filter(etablissement=self.etablissement, is_active=True).first()
            annee_str = annee.libelle[-4:] if annee else str(timezone.now().year)
            self.matricule = self._generer_matricule_atomique(self.etablissement, annee_str)
        super().save(*args, **kwargs)

    @property
    def nom_complet(self): return f"{self.nom} {self.prenom}"

    @property
    def age(self):
        today = timezone.now().date()
        return today.year - self.date_naissance.year - ((today.month, today.day) < (self.date_naissance.month, self.date_naissance.day))

    def get_inscription_active(self):
        return self.inscriptions.filter(is_active=True).first()


class Tuteur(models.Model):
    LIENS = [('pere','Pere'),('mere','Mere'),('tuteur','Tuteur legal')]
    etablissement = models.ForeignKey('etablissements.Etablissement', on_delete=models.CASCADE)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    lien = models.CharField(max_length=20, choices=LIENS, default='pere')
    telephone = models.CharField(max_length=20)
    telephone2 = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    profession = models.CharField(max_length=100, blank=True)
    user_compte = models.OneToOneField('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='profil_tuteur', help_text="Compte de connexion du parent (optionnel)")

    def __str__(self): return f"{self.nom} {self.prenom} ({self.get_lien_display()})"


class Inscription(models.Model):
    STATUTS = [('actif','Actif'),('transfere','Transfere'),('exclu','Exclu'),('suspendu','Suspendu')]
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name='inscriptions')
    classe = models.ForeignKey('etablissements.Classe', on_delete=models.CASCADE, related_name='inscriptions')
    annee = models.ForeignKey('etablissements.AnneeScolaire', on_delete=models.CASCADE)
    statut = models.CharField(max_length=20, choices=STATUTS, default='actif')
    is_active = models.BooleanField(default=True)
    date_inscription = models.DateField(default=timezone.now)
    observations = models.TextField(blank=True)

    class Meta:
        unique_together = ['eleve','annee']

    def __str__(self): return f"{self.eleve.nom_complet} -> {self.classe.nom}"


class Presence(models.Model):
    STATUTS = [('present','Present'),('absent','Absent'),('retard','En retard'),('justifie','Justifie')]
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name='presences')
    classe = models.ForeignKey('etablissements.Classe', on_delete=models.CASCADE, related_name='presences')
    date = models.DateField()
    statut = models.CharField(max_length=15, choices=STATUTS, default='present')
    motif = models.CharField(max_length=200, blank=True)
    justificatif_valide = models.BooleanField(default=False)
    enregistre_par = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)

    class Meta:
        unique_together = ['eleve','date','classe']
        ordering = ['-date']

    def __str__(self): return f"{self.eleve.nom_complet} — {self.date} — {self.get_statut_display()}"
