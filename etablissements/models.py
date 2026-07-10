from django.db import models

class Etablissement(models.Model):
    TYPES = [
        ('ecole','Ecole Fondamentale'),('lycee','Lycee'),
        ('universite','Universite'),('centre','Centre de Formation'),('institut','Institut'),
    ]
    nom = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=TYPES, default='ecole')
    code = models.CharField(max_length=20, unique=True)
    logo = models.ImageField(upload_to='etablissements/logos/', blank=True, null=True)
    adresse = models.TextField(blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    directeur = models.CharField(max_length=200, blank=True)
    slogan = models.CharField(max_length=300, blank=True)
    couleur_principale = models.CharField(max_length=7, default='#1565C0')
    couleur_secondaire = models.CharField(max_length=7, default='#0D47A1')
    is_active = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self): return self.nom


class AnneeScolaire(models.Model):
    etablissement = models.ForeignKey(Etablissement, on_delete=models.CASCADE, related_name='annees')
    libelle = models.CharField(max_length=20)
    date_debut = models.DateField()
    date_fin = models.DateField()
    is_active = models.BooleanField(default=False)

    class Meta:
        unique_together = ['etablissement','libelle']
        ordering = ['-libelle']

    def __str__(self): return f"{self.libelle} — {self.etablissement.nom}"

    def save(self, *args, **kwargs):
        if self.is_active:
            AnneeScolaire.objects.filter(etablissement=self.etablissement).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


class Niveau(models.Model):
    etablissement = models.ForeignKey(Etablissement, on_delete=models.CASCADE, related_name='niveaux')
    cycle         = models.ForeignKey('Cycle', on_delete=models.SET_NULL, null=True, blank=True, related_name='niveaux')
    nom = models.CharField(max_length=100)
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['ordre']
        unique_together = ['etablissement','nom']

    def __str__(self): return self.nom


class Classe(models.Model):
    etablissement = models.ForeignKey(Etablissement, on_delete=models.CASCADE, related_name='classes')
    annee = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE, related_name='classes')
    niveau = models.ForeignKey(Niveau, on_delete=models.CASCADE, related_name='classes')
    serie    = models.ForeignKey('SerieLycee', on_delete=models.SET_NULL, null=True, blank=True, related_name='classes', help_text="Serie lycee uniquement")
    division  = models.ForeignKey('Division', on_delete=models.SET_NULL, null=True, blank=True, related_name='classes_directes', help_text="Division administrative (si etablissement multi-cycles)")
    filiere   = models.CharField(max_length=150, blank=True, help_text="Filière universitaire (ex: Informatique, Droit, Médecine...)")
    semestre_actif = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Semestre en cours (université)")
    nom = models.CharField(max_length=100)
    capacite_max = models.PositiveIntegerField(default=40)
    salle = models.CharField(max_length=50, blank=True)
    professeur_principal = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='classes_principales')

    class Meta:
        unique_together = ['etablissement','annee','nom']
        ordering = ['niveau__ordre','nom']

    def __str__(self): return f"{self.nom} — {self.annee.libelle}"

    @property
    def nombre_eleves(self): return self.inscriptions.filter(is_active=True).count()

    @property
    def taux_remplissage(self):
        return int((self.nombre_eleves / self.capacite_max) * 100) if self.capacite_max else 0


class Enseignant(models.Model):
    STATUTS = [('actif','Actif'),('conge','En conge'),('inactif','Inactif')]
    user = models.OneToOneField('accounts.User', on_delete=models.CASCADE, related_name='profil_enseignant')
    etablissement = models.ForeignKey(Etablissement, on_delete=models.CASCADE, related_name='enseignants')
    matricule_pro = models.CharField(max_length=30, blank=True)
    specialite = models.CharField(max_length=200, blank=True)
    diplome = models.CharField(max_length=200, blank=True)
    date_embauche = models.DateField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUTS, default='actif')
    salaire = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)

    def __str__(self): return self.user.get_full_name() or self.user.username

    @property
    def nom_complet(self): return self.user.get_full_name() or self.user.username


class AffectationMatiere(models.Model):
    enseignant = models.ForeignKey(Enseignant, on_delete=models.CASCADE, related_name='affectations')
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name='affectations')
    matiere = models.ForeignKey('notes.Matiere', on_delete=models.CASCADE)
    annee = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE)
    heures_semaine = models.PositiveIntegerField(default=2)

    class Meta:
        unique_together = ['enseignant','classe','matiere','annee']

    def __str__(self): return f"{self.enseignant} -> {self.matiere} ({self.classe.nom})"


class ParametreEtablissement(models.Model):
    etablissement = models.OneToOneField(Etablissement, on_delete=models.CASCADE, related_name='parametres')
    devise = models.CharField(max_length=10, default='FCFA')
    type_periode = models.CharField(max_length=20, choices=[('trimestre','Trimestres'),('semestre','Semestres')], default='trimestre')
    note_passage = models.DecimalField(max_digits=4, decimal_places=2, default=10)
    note_max = models.DecimalField(max_digits=4, decimal_places=2, default=20)
    entete_bulletin = models.TextField(blank=True)
    pied_bulletin = models.TextField(blank=True)

    def __str__(self): return f"Parametres — {self.etablissement.nom}"


class ModeleDocument(models.Model):
    TYPES = [
        ('bulletin','Bulletin de notes'),('recu','Recu de paiement'),
        ('certificat','Certificat de scolarite'),('attestation','Attestation de frequentation'),
        ('carte_scolaire','Carte scolaire'),('releve_notes','Releve de notes'),
    ]
    etablissement = models.ForeignKey(Etablissement, on_delete=models.CASCADE, related_name='modeles_documents')
    type_document = models.CharField(max_length=30, choices=TYPES)
    nom = models.CharField(max_length=100)
    is_actif = models.BooleanField(default=True)
    # En-tête
    afficher_logo = models.BooleanField(default=True)
    ligne1_gauche = models.CharField(max_length=200, blank=True)
    ligne2_gauche = models.CharField(max_length=200, blank=True)
    ligne3_gauche = models.CharField(max_length=200, blank=True)
    ligne1_droite = models.CharField(max_length=200, blank=True)
    ligne2_droite = models.CharField(max_length=200, blank=True)
    ligne3_droite = models.CharField(max_length=200, blank=True)
    nom_etablissement_custom = models.CharField(max_length=200, blank=True)
    sous_titre_etablissement = models.CharField(max_length=200, blank=True)
    afficher_adresse = models.BooleanField(default=True)
    afficher_telephone = models.BooleanField(default=True)
    # Titre
    titre_document = models.CharField(max_length=100, blank=True)
    couleur_titre_bg = models.CharField(max_length=7, default='#555555')
    couleur_titre_texte = models.CharField(max_length=7, default='#ffffff')
    # Style
    couleur_tableau_header = models.CharField(max_length=7, default='#dddddd')
    couleur_tableau_texte = models.CharField(max_length=7, default='#000000')
    couleur_bordure = models.CharField(max_length=7, default='#000000')
    police = models.CharField(max_length=30, default='Arial', choices=[('Arial','Arial'),('Times New Roman','Times New Roman'),('Calibri','Calibri'),('Georgia','Georgia')])
    taille_police = models.PositiveIntegerField(default=13)
    # Colonnes bulletin
    col_moy_classe = models.BooleanField(default=True)
    col_moy_compo = models.BooleanField(default=True)
    col_moyenne_finale = models.BooleanField(default=True)
    col_coefficient = models.BooleanField(default=True)
    col_moy_coeffic = models.BooleanField(default=True)
    col_appreciation = models.BooleanField(default=True)
    note_max_classe = models.PositiveIntegerField(default=20)
    note_max_compo = models.PositiveIntegerField(default=40)
    afficher_moy_premier = models.BooleanField(default=True)
    afficher_rang = models.BooleanField(default=True)
    afficher_appre_directeur = models.BooleanField(default=True)
    label_signature_gauche = models.CharField(max_length=100, default='Le Directeur')
    label_signature_droite = models.CharField(max_length=100, default='Le Parent ou Tuteur')
    texte_pied_page = models.TextField(blank=True)
    afficher_date = models.BooleanField(default=True)
    format_recu = models.CharField(max_length=10, default='A5', choices=[('ticket','Ticket 80mm'),('A5','A5'),('A4','A4')])
    couleur_accent_recu = models.CharField(max_length=7, default='#1565C0')
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['etablissement','type_document','nom']

    def __str__(self): return f"{self.get_type_document_display()} — {self.nom}"


# ══════════════════════════════════════════════════════════════
#  CYCLES SCOLAIRES — Système malien
# ══════════════════════════════════════════════════════════════

class Cycle(models.Model):
    TYPES = [
        ('premier_cycle', '1er Cycle Fondamental (1ère–6ème)'),
        ('second_cycle',  '2ème Cycle Fondamental (7ème–9ème)'),
        ('lycee',         'Lycée (10ème–12ème / Seconde–Terminale)'),
        ('universite',    'Université (Licence, Master, Doctorat)'),
    ]
    MODE_CALCUL = [
        ('compo',  'Moy.Classe /20 + Moy.Compo /40 → /20'),
        ('direct', 'Note directe /20'),
        ('credit', 'Crédits ECTS / UE (Université)'),
    ]
    etablissement   = models.ForeignKey('Etablissement', on_delete=models.CASCADE, related_name='cycles')
    type_cycle      = models.CharField(max_length=20, choices=TYPES)
    nom             = models.CharField(max_length=100)
    mode_calcul     = models.CharField(max_length=10, choices=MODE_CALCUL, default='compo')
    note_passage    = models.DecimalField(max_digits=4, decimal_places=2, default=10)
    note_max        = models.DecimalField(max_digits=4, decimal_places=2, default=20)
    # Diplôme préparé
    diplome_prepare = models.CharField(max_length=100, blank=True,
        help_text="Ex: DEF, BAC, Licence... Apparait sur les documents")
    # Ordre d'affichage
    ordre           = models.PositiveSmallIntegerField(default=1)
    is_active       = models.BooleanField(default=True)
    date_creation   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['ordre']
        unique_together = [['etablissement', 'type_cycle']]
        verbose_name = 'Cycle scolaire'

    def __str__(self):
        return f"{self.nom} ({self.get_type_cycle_display()})"

    @property
    def is_universite(self):
        return self.type_cycle == 'universite'

    @property
    def is_lycee(self):
        return self.type_cycle == 'lycee'

    @property
    def utilise_compo(self):
        return self.mode_calcul == 'compo'

    @property
    def utilise_credits(self):
        return self.mode_calcul == 'credit'


class MatiereCycle(models.Model):
    """Matières par défaut d'un cycle avec leurs coefficients."""
    cycle           = models.ForeignKey(Cycle, on_delete=models.CASCADE, related_name='matieres_defaut')
    matiere         = models.ForeignKey('notes.Matiere', on_delete=models.CASCADE)
    coefficient     = models.PositiveSmallIntegerField(default=1)
    est_obligatoire = models.BooleanField(default=True)
    ordre           = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ['ordre']
        unique_together = [['cycle', 'matiere']]

    def __str__(self):
        return f"{self.cycle.nom} — {self.matiere.nom} (coef {self.coefficient})"


class SerieLycee(models.Model):
    """Séries du lycée malien : A (Lettres), B (Sciences Sociales), C (Maths/Physique), D (SVT)."""
    cycle   = models.ForeignKey(Cycle, on_delete=models.CASCADE, related_name='series')
    code    = models.CharField(max_length=5, help_text="Ex: A, B, C, D")
    nom     = models.CharField(max_length=100, help_text="Ex: Sciences Exactes")
    ordre   = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ['ordre']

    def __str__(self):
        return f"Serie {self.code} — {self.nom}"


class MatiereSerieCoef(models.Model):
    """Coefficient d'une matière selon la série du lycée."""
    serie       = models.ForeignKey(SerieLycee, on_delete=models.CASCADE, related_name='coefficients')
    matiere     = models.ForeignKey('notes.Matiere', on_delete=models.CASCADE)
    coefficient = models.PositiveSmallIntegerField(default=1)
    est_obligatoire = models.BooleanField(default=True)

    class Meta:
        unique_together = [['serie', 'matiere']]

    def __str__(self):
        return f"{self.serie} — {self.matiere.nom} coef {self.coefficient}"


class UEUniversite(models.Model):
    """Unité d'Enseignement pour l'université (système LMD)."""
    SEMESTRES = [(i, f"Semestre {i}") for i in range(1, 9)]
    cycle       = models.ForeignKey(Cycle, on_delete=models.CASCADE, related_name='ues')
    code        = models.CharField(max_length=20, help_text="Ex: UE101, MATH-L1")
    nom         = models.CharField(max_length=200)
    credits     = models.PositiveSmallIntegerField(default=3, help_text="Crédits ECTS")
    semestre    = models.PositiveSmallIntegerField(choices=SEMESTRES, default=1)
    coefficient = models.PositiveSmallIntegerField(default=1)
    est_obligatoire = models.BooleanField(default=True)

    class Meta:
        ordering = ['semestre', 'code']

    def __str__(self):
        return f"[S{self.semestre}] {self.code} — {self.nom} ({self.credits} cr.)"


# ══════════════════════════════════════════════════════════════
#  OPTION A+B : Cycles actifs + Divisions par cycle
# ══════════════════════════════════════════════════════════════

class CycleActif(models.Model):
    """
    Option A : Déclare quels cycles sont actifs dans un établissement.
    Si un seul cycle → interface simplifiée.
    Si plusieurs → option divisions disponible.
    """
    etablissement = models.ForeignKey('Etablissement', on_delete=models.CASCADE,
                                       related_name='cycles_actifs')
    cycle         = models.ForeignKey('Cycle', on_delete=models.CASCADE)
    is_active     = models.BooleanField(default=True)
    ordre         = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ['ordre']
        unique_together = [['etablissement', 'cycle']]

    def __str__(self):
        return f"{self.etablissement.nom} → {self.cycle.nom}"


class Division(models.Model):
    """
    Option B : Subdivision administrative d'un établissement par cycle(s).
    Chaque division a son propre directeur, comptable, surveillant,
    logo, en-tête de documents.
    Ex: "Fondamental", "Lycée", "Université"
    """
    etablissement   = models.ForeignKey('Etablissement', on_delete=models.CASCADE,
                                         related_name='divisions')
    nom             = models.CharField(max_length=100,
                                        help_text="Ex: Fondamental, Lycée, Section Technique")
    code            = models.CharField(max_length=20, blank=True,
                                        help_text="Ex: FOND, LYC, UNIV")
    # Cycles couverts par cette division
    cycles          = models.ManyToManyField('Cycle', related_name='divisions', blank=True)
    # Administration propre
    directeur_nom   = models.CharField(max_length=150, blank=True)
    directeur_user  = models.ForeignKey('accounts.User', on_delete=models.SET_NULL,
                                         null=True, blank=True,
                                         related_name='divisions_dirigees')
    # Identité visuelle propre (optionnel — hérite de l'établissement si vide)
    logo            = models.ImageField(upload_to='divisions/logos/', blank=True, null=True)
    adresse         = models.TextField(blank=True,
                                        help_text="Laisser vide pour hériter de l'établissement")
    telephone       = models.CharField(max_length=30, blank=True)
    slogan          = models.CharField(max_length=200, blank=True)
    # En-tête documents propre
    entete_ligne1   = models.CharField(max_length=200, blank=True)
    entete_ligne2   = models.CharField(max_length=200, blank=True)
    couleur_principale = models.CharField(max_length=7, default='#1565C0')
    # Ordre d'affichage
    ordre           = models.PositiveSmallIntegerField(default=1)
    is_active       = models.BooleanField(default=True)
    date_creation   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['ordre']
        unique_together = [['etablissement', 'nom']]
        verbose_name = 'Division'

    def __str__(self):
        return f"{self.etablissement.code} — {self.nom}"

    def get_logo(self):
        """Retourne le logo de la division ou celui de l'établissement."""
        return self.logo if self.logo else self.etablissement.logo

    def get_adresse(self):
        return self.adresse or self.etablissement.adresse

    def get_telephone(self):
        return self.telephone or self.etablissement.telephone

    @property
    def nb_classes(self):
        cycles_ids = self.cycles.values_list('pk', flat=True)
        return Classe.objects.filter(
            etablissement=self.etablissement,
            niveau__cycle__in=cycles_ids
        ).count()

    @property
    def nb_eleves(self):
        from eleves.models import Inscription
        cycles_ids = self.cycles.values_list('pk', flat=True)
        return Inscription.objects.filter(
            classe__etablissement=self.etablissement,
            classe__niveau__cycle__in=cycles_ids,
            is_active=True
        ).count()
