from django.db import models
from django.utils import timezone


class Matiere(models.Model):
    etablissement = models.ForeignKey('etablissements.Etablissement', on_delete=models.CASCADE)
    nom = models.CharField(max_length=100)
    code = models.CharField(max_length=10, blank=True)
    coefficient = models.PositiveIntegerField(default=1)
    description = models.TextField(blank=True)
    # Conduite = gérée par le surveillant, note unique par période
    is_conduite = models.BooleanField(default=False, help_text="Matiere de conduite/comportement")

    class Meta:
        ordering = ['nom']
        unique_together = ['etablissement','nom']

    def __str__(self): return f"{self.nom} (coef.{self.coefficient})"


class Periode(models.Model):
    etablissement = models.ForeignKey('etablissements.Etablissement', on_delete=models.CASCADE)
    annee = models.ForeignKey('etablissements.AnneeScolaire', on_delete=models.CASCADE)
    type = models.CharField(max_length=20, choices=[('trimestre','Trimestre'),('semestre','Semestre')], default='trimestre')
    numero = models.PositiveIntegerField()
    libelle = models.CharField(max_length=50)
    date_debut = models.DateField()
    date_fin = models.DateField()
    is_active = models.BooleanField(default=False)
    # P2.2 — Clôture de saisie : une fois verrouillée, aucun enseignant
    # ne peut plus modifier les notes. Seul un admin peut réouvrir.
    saisie_cloturee = models.BooleanField(
        default=False,
        help_text="Si vrai, toute saisie/modification de notes est bloquée sur cette période."
    )
    date_cloture = models.DateTimeField(
        null=True, blank=True,
        help_text="Date à laquelle la saisie a été clôturée."
    )
    cloture_par = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='periodes_cloturees',
        help_text="Administrateur ayant clôturé la saisie."
    )

    class Meta:
        ordering = ['numero']
        unique_together = ['etablissement','annee','numero']

    def __str__(self): return f"{self.libelle} — {self.annee.libelle}"

    @property
    def peut_saisir(self):
        """
        Retourne True si la période autorise encore la saisie de notes.
        Une période clôturée bloque toute modification par les enseignants.
        Les admins peuvent forcer la saisie même après clôture en réouvrant.
        """
        return not self.saisie_cloturee


class NoteUE(models.Model):
    """Note d'une Unité d'Enseignement pour l'université (système LMD)."""
    eleve           = models.ForeignKey('eleves.Eleve', on_delete=models.CASCADE, related_name='notes_ue')
    ue              = models.ForeignKey('etablissements.UEUniversite', on_delete=models.CASCADE, related_name='notes')
    classe          = models.ForeignKey('etablissements.Classe', on_delete=models.CASCADE)
    periode         = models.ForeignKey('Periode', on_delete=models.CASCADE)
    note            = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, help_text="Note /20")
    note_rattrapage = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, help_text="Note de rattrapage /20")
    credits_valides = models.BooleanField(default=False, help_text="Crédits validés (note >= 10)")
    mention         = models.CharField(max_length=20, blank=True)
    saisi_par       = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='notes_ue_saisies')
    date_saisie     = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['eleve', 'ue', 'classe', 'periode']]
        ordering = ['ue__semestre', 'ue__code']

    def __str__(self):
        return f"{self.eleve.nom_complet} — {self.ue.code} — {self.note or '—'}/20"

    def save(self, *args, **kwargs):
        # Calculer la validation et la mention automatiquement
        note_finale = self.note_rattrapage if (self.note_rattrapage and self.note and self.note_rattrapage > self.note) else self.note
        if note_finale is not None:
            self.credits_valides = float(note_finale) >= 10
            if float(note_finale) >= 16: self.mention = 'Très Bien'
            elif float(note_finale) >= 14: self.mention = 'Bien'
            elif float(note_finale) >= 12: self.mention = 'Assez Bien'
            elif float(note_finale) >= 10: self.mention = 'Passable'
            else: self.mention = 'Insuffisant'
        super().save(*args, **kwargs)

    @property
    def note_retenue(self):
        """Note finale (rattrapage si meilleure)."""
        if self.note_rattrapage and self.note and self.note_rattrapage > self.note:
            return self.note_rattrapage
        return self.note


class NotePeriode(models.Model):
    """Note format malien : moy_classe + moy_compo par matière/élève/période."""
    eleve    = models.ForeignKey('eleves.Eleve', on_delete=models.CASCADE, related_name='notes_periode')
    matiere  = models.ForeignKey(Matiere, on_delete=models.CASCADE)
    classe   = models.ForeignKey('etablissements.Classe', on_delete=models.CASCADE)
    periode  = models.ForeignKey(Periode, on_delete=models.CASCADE)
    # Pour les matières normales : deux colonnes
    moy_classe = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    moy_compo  = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    note_max_classe = models.DecimalField(max_digits=5, decimal_places=2, default=20)
    note_max_compo  = models.DecimalField(max_digits=5, decimal_places=2, default=40)
    # Pour la conduite : note unique sur 20
    note_conduite = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    # Sécurité : qui a saisi et modifié
    saisi_par    = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, related_name='notes_saisies')
    modifie_par  = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='notes_modifiees')
    date_saisie  = models.DateTimeField(auto_now_add=True)
    date_modif   = models.DateTimeField(auto_now=True)
    valeur_avant_modif = models.CharField(max_length=100, blank=True, help_text="Sauvegarde avant modification")

    class Meta:
        unique_together = ['eleve','matiere','classe','periode']
        verbose_name = 'Note de periode'

    def __str__(self): return f"{self.eleve} — {self.matiere.nom} — {self.periode.libelle}"

    @property
    def moyenne_finale(self):
        if self.matiere.is_conduite:
            return float(self.note_conduite) if self.note_conduite is not None else None
        if self.moy_classe is not None and self.moy_compo is not None:
            mc20 = (float(self.moy_classe) / float(self.note_max_classe)) * 20
            mn20 = (float(self.moy_compo)  / float(self.note_max_compo))  * 20
            return round((mc20 + mn20) / 2, 2)
        elif self.moy_classe is not None:
            return round((float(self.moy_classe) / float(self.note_max_classe)) * 20, 2)
        return None

    @property
    def moy_coeffic(self):
        moy = self.moyenne_finale
        return round(moy * self.matiere.coefficient, 2) if moy is not None else None

    @property
    def appreciation(self):
        moy = self.moyenne_finale
        if moy is None: return ''
        if moy >= 16: return 'Tres-Bien'
        if moy >= 14: return 'Bien'
        if moy >= 12: return 'Assez-Bien'
        if moy >= 10: return 'Passable'
        if moy >= 6:  return 'Mal'
        return 'Tres Mal'


class LogModificationNote(models.Model):
    """Journal de toutes les modifications de notes."""
    note_periode  = models.ForeignKey(NotePeriode, on_delete=models.CASCADE, related_name='logs')
    modifie_par   = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
    role_modifiant = models.CharField(max_length=20)
    # Valeurs avant/après
    champ_modifie = models.CharField(max_length=30)
    valeur_avant  = models.CharField(max_length=50, blank=True)
    valeur_apres  = models.CharField(max_length=50, blank=True)
    date_modif    = models.DateTimeField(auto_now_add=True)
    # Notification envoyée au directeur ?
    notif_envoyee = models.BooleanField(default=False)
    notif_lue     = models.BooleanField(default=False)

    class Meta:
        ordering = ['-date_modif']
        verbose_name = 'Log modification note'

    def __str__(self):
        return f"{self.modifie_par} modifié {self.champ_modifie} le {self.date_modif.strftime('%d/%m/%Y %H:%M')}"


class EmploiDuTemps(models.Model):
    JOURS = [
        ('lundi','Lundi'),('mardi','Mardi'),('mercredi','Mercredi'),
        ('jeudi','Jeudi'),('vendredi','Vendredi'),('samedi','Samedi'),
    ]
    etablissement = models.ForeignKey('etablissements.Etablissement', on_delete=models.CASCADE)
    classe    = models.ForeignKey('etablissements.Classe', on_delete=models.CASCADE, related_name='emplois')
    matiere   = models.ForeignKey(Matiere, on_delete=models.CASCADE)
    enseignant = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    jour      = models.CharField(max_length=10, choices=JOURS)
    heure_debut = models.CharField(max_length=5)
    heure_fin   = models.CharField(max_length=5)
    salle     = models.CharField(max_length=50, blank=True)

    def __str__(self): return f"{self.classe.nom} — {self.jour} {self.heure_debut}-{self.heure_fin} — {self.matiere.nom}"


class Bulletin(models.Model):
    eleve    = models.ForeignKey('eleves.Eleve', on_delete=models.CASCADE, related_name='bulletins')
    classe   = models.ForeignKey('etablissements.Classe', on_delete=models.CASCADE)
    periode  = models.ForeignKey(Periode, on_delete=models.CASCADE)
    annee    = models.ForeignKey('etablissements.AnneeScolaire', on_delete=models.CASCADE)
    moyenne_generale = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    rang     = models.PositiveIntegerField(null=True, blank=True)
    effectif_classe = models.PositiveIntegerField(null=True, blank=True)
    appreciation = models.TextField(blank=True)
    is_valide = models.BooleanField(default=False)
    date_generation = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['eleve','periode']

    def get_mention(self):
        if self.moyenne_generale is None: return ''
        m = float(self.moyenne_generale)
        if m >= 16: return 'Tres Bien'
        if m >= 14: return 'Bien'
        if m >= 12: return 'Assez Bien'
        if m >= 10: return 'Passable'
        return 'Insuffisant'


class Reclamation(models.Model):
    """Reclamation d'un parent ou eleve concernant une note."""
    STATUTS = [
        ('en_attente', 'En attente'),
        ('en_cours', 'En cours de traitement'),
        ('acceptee', 'Acceptee'),
        ('rejetee', 'Rejetee'),
    ]
    note_periode = models.ForeignKey(NotePeriode, on_delete=models.CASCADE, related_name='reclamations')
    eleve = models.ForeignKey('eleves.Eleve', on_delete=models.CASCADE, related_name='reclamations')
    auteur = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, related_name='reclamations_envoyees')
    role_auteur = models.CharField(max_length=20, blank=True)
    motif = models.TextField(help_text="Explication de la reclamation")
    statut = models.CharField(max_length=20, choices=STATUTS, default='en_attente')
    reponse = models.TextField(blank=True, help_text="Reponse de l'administration")
    traite_par = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='reclamations_traitees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_traitement = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-date_creation']
        verbose_name = 'Reclamation'

    def __str__(self):
        return f"Reclamation {self.eleve.nom_complet} — {self.note_periode.matiere.nom} — {self.get_statut_display()}"


class MessageFamille(models.Model):
    """Message envoye par un parent ou eleve vers l'administration."""
    DESTINATAIRES = [
        ('directeur',  'Directeur'),
        ('comptable',  'Comptable'),
        ('surveillant','Surveillant General'),
        ('enseignant', 'Enseignant (matiere concernee)'),
        ('administration', 'Administration (tous)'),
    ]
    STATUTS = [
        ('non_lu', 'Non lu'),
        ('lu',     'Lu'),
        ('repondu','Repondu'),
    ]
    etablissement    = models.ForeignKey('etablissements.Etablissement', on_delete=models.CASCADE)
    expediteur       = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='messages_envoyes')
    eleve            = models.ForeignKey('eleves.Eleve', on_delete=models.SET_NULL, null=True, blank=True, related_name='messages')
    destinataire_role = models.CharField(max_length=20, choices=DESTINATAIRES)
    destinataire_user = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='messages_recus')
    sujet            = models.CharField(max_length=200)
    corps            = models.TextField()
    statut           = models.CharField(max_length=10, choices=STATUTS, default='non_lu')
    reponse          = models.TextField(blank=True)
    repondu_par      = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='messages_repondus')
    date_envoi       = models.DateTimeField(auto_now_add=True)
    date_reponse     = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-date_envoi']
        verbose_name = 'Message famille'

    def __str__(self):
        return f"{self.expediteur} → {self.get_destinataire_role_display()} : {self.sujet}"
