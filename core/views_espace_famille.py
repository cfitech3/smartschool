"""
Espace dedie aux parents et eleves : consultation en lecture seule
de leurs propres donnees (notes, absences, bulletin) + reclamations.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from eleves.models import Eleve, Presence
from notes.models import NotePeriode, Periode, Matiere, Reclamation
from notes.views_notes import calculer_bulletin
from etablissements.models import AnneeScolaire


def get_eleves_accessibles(user):
    """
    Renvoie la liste des eleves que cet utilisateur a le droit de consulter.
    - role 'eleve' -> uniquement lui-meme (via profil_eleve)
    - role 'parent' -> tous les enfants rattaches a son profil_tuteur
    """
    if user.is_eleve_user and hasattr(user, 'profil_eleve') and user.profil_eleve:
        return Eleve.objects.filter(pk=user.profil_eleve.pk)
    if user.is_parent and hasattr(user, 'profil_tuteur') and user.profil_tuteur:
        return Eleve.objects.filter(tuteur=user.profil_tuteur, is_active=True)
    return Eleve.objects.none()


def require_famille(fn):
    def wrapper(request, *args, **kwargs):
        if not (request.user.is_parent or request.user.is_eleve_user):
            messages.error(request, "Acces reserve aux parents et eleves.")
            return redirect('dashboard')
        return fn(request, *args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper


def get_eleve_ou_403(request, eleve_pk):
    """Recupere l'eleve seulement s'il est dans le perimetre autorise."""
    eleves_ok = get_eleves_accessibles(request.user)
    return get_object_or_404(eleves_ok, pk=eleve_pk)


@login_required
@require_famille
def espace_accueil(request):
    """Page d'accueil : liste des enfants (parent) ou redirection directe (eleve)."""
    eleves = get_eleves_accessibles(request.user)
    if request.user.is_eleve_user and eleves.count() == 1:
        return redirect('espace_eleve_detail', eleve_pk=eleves.first().pk)
    return render(request, 'core/famille/accueil.html', {'eleves': eleves})


@login_required
@require_famille
def espace_eleve_detail(request, eleve_pk):
    eleve = get_eleve_ou_403(request, eleve_pk)
    etab = eleve.etablissement
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
    periodes = Periode.objects.filter(etablissement=etab, annee=annee) if annee else []
    periode_active = periodes.filter(is_active=True).first() if periodes else None
    inscription = eleve.get_inscription_active()

    # Resume notes (periode active)
    moy_generale = None
    if periode_active:
        matieres = Matiere.objects.filter(etablissement=etab)
        _, moy_generale, _, _ = calculer_bulletin(eleve, periode_active, matieres)

    # Resume absences (30 derniers jours)
    from django.utils import timezone
    import datetime
    depuis = timezone.now().date() - datetime.timedelta(days=30)
    nb_absences = Presence.objects.filter(eleve=eleve, statut='absent', date__gte=depuis).count()
    nb_retards = Presence.objects.filter(eleve=eleve, statut='retard', date__gte=depuis).count()

    # Reclamations en cours
    nb_reclamations_attente = Reclamation.objects.filter(eleve=eleve, statut__in=['en_attente','en_cours']).count()

    return render(request, 'core/famille/eleve_detail.html', {
        'eleve': eleve, 'inscription': inscription, 'periode_active': periode_active,
        'moy_generale': moy_generale, 'nb_absences': nb_absences, 'nb_retards': nb_retards,
        'nb_reclamations_attente': nb_reclamations_attente, 'annee': annee,
    })


@login_required
@require_famille
def espace_notes(request, eleve_pk):
    eleve = get_eleve_ou_403(request, eleve_pk)
    etab = eleve.etablissement
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
    periodes = Periode.objects.filter(etablissement=etab, annee=annee) if annee else []
    periode_id = request.GET.get('periode')
    periode = get_object_or_404(Periode, pk=periode_id, etablissement=etab) if periode_id else periodes.filter(is_active=True).first()

    lignes, moy_gen, total_coeffic, total_coef = ([], None, 0, 0)
    if periode:
        matieres = Matiere.objects.filter(etablissement=etab)
        lignes, moy_gen, total_coeffic, total_coef = calculer_bulletin(eleve, periode, matieres)
        # IDs des notes pour permettre la reclamation
        for l in lignes:
            note_obj = NotePeriode.objects.filter(eleve=eleve, matiere=l['matiere'], periode=periode).first()
            l['note_id'] = note_obj.pk if note_obj else None
            l['a_reclamation'] = Reclamation.objects.filter(note_periode=note_obj).exists() if note_obj else False

    return render(request, 'core/famille/notes.html', {
        'eleve': eleve, 'periodes': periodes, 'periode': periode,
        'lignes': lignes, 'moy_generale': moy_gen,
    })


@login_required
@require_famille
def espace_absences(request, eleve_pk):
    eleve = get_eleve_ou_403(request, eleve_pk)
    base_qs = Presence.objects.filter(eleve=eleve)
    stats = {
        'total': base_qs.count(),
        'absents': base_qs.filter(statut='absent').count(),
        'retards': base_qs.filter(statut='retard').count(),
        'justifies': base_qs.filter(statut='justifie').count(),
    }
    presences = base_qs.order_by('-date')[:60]
    return render(request, 'core/famille/absences.html', {'eleve': eleve, 'presences': presences, 'stats': stats})


@login_required
@require_famille
def espace_bulletin(request, eleve_pk, periode_pk):
    eleve = get_eleve_ou_403(request, eleve_pk)
    # Reutilise directement la vue bulletin existante (lecture seule, format imprimable)
    from notes.views_notes import bulletin_eleve
    return bulletin_eleve(request, eleve_pk=eleve.pk, periode_pk=periode_pk)


@login_required
@require_famille
def espace_reclamations(request, eleve_pk):
    eleve = get_eleve_ou_403(request, eleve_pk)
    reclamations = Reclamation.objects.filter(eleve=eleve).select_related('note_periode__matiere', 'note_periode__periode', 'traite_par')
    return render(request, 'core/famille/reclamations.html', {'eleve': eleve, 'reclamations': reclamations})


@login_required
@require_famille
def creer_reclamation(request, eleve_pk, note_pk):
    eleve = get_eleve_ou_403(request, eleve_pk)
    note = get_object_or_404(NotePeriode, pk=note_pk, eleve=eleve)

    if Reclamation.objects.filter(note_periode=note, statut__in=['en_attente','en_cours']).exists():
        messages.warning(request, "Une reclamation est deja en cours pour cette note.")
        return redirect('espace_notes', eleve_pk=eleve.pk)

    if request.method == 'POST':
        motif = request.POST.get('motif', '').strip()
        if not motif:
            messages.error(request, "Veuillez expliquer le motif de la reclamation.")
        else:
            Reclamation.objects.create(
                note_periode=note, eleve=eleve, auteur=request.user,
                role_auteur=request.user.role, motif=motif,
            )
            messages.success(request, "Reclamation envoyee. La direction va l'examiner.")
            return redirect('espace_reclamations', eleve_pk=eleve.pk)

    return render(request, 'core/famille/form_reclamation.html', {'eleve': eleve, 'note': note})




@login_required
@require_famille
def espace_paiements(request, eleve_pk):
    """Paiements effectues et situation financiere."""
    eleve = get_eleve_ou_403(request, eleve_pk)
    etab = eleve.etablissement
    from etablissements.models import AnneeScolaire
    from finances.models import Paiement, TypeFrais
    from django.db.models import Sum
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()

    # Paiements effectues cette annee
    paiements = Paiement.objects.filter(
        eleve=eleve, annee=annee, statut='valide'
    ).select_related('type_frais').order_by('-date_paiement') if annee else []

    total_paye = paiements.aggregate(t=Sum('montant'))['t'] or 0 if paiements else 0

    # Frais attendus vs payes (frais obligatoires)
    types_obligatoires = TypeFrais.objects.filter(etablissement=etab, is_obligatoire=True)
    frais_attendus = []
    for tf in types_obligatoires:
        paye = paiements.filter(type_frais=tf).aggregate(t=Sum('montant'))['t'] or 0 if paiements else 0
        attendu = tf.montant_defaut
        frais_attendus.append({
            'type': tf,
            'attendu': attendu,
            'paye': paye,
            'solde': paye - attendu,
            'en_retard': paye < attendu,
        })

    nb_retards = sum(1 for f in frais_attendus if f['en_retard'])

    return render(request, 'core/famille/paiements.html', {
        'eleve': eleve, 'paiements': paiements, 'annee': annee,
        'total_paye': total_paye, 'frais_attendus': frais_attendus,
        'nb_retards': nb_retards,
    })



@login_required
@require_famille
def espace_emploi_du_temps(request, eleve_pk):
    """Emploi du temps de la classe de l'élève."""
    eleve = get_eleve_ou_403(request, eleve_pk)
    inscription = eleve.get_inscription_active()
    creneaux = []
    if inscription:
        from notes.models import EmploiDuTemps
        creneaux = EmploiDuTemps.objects.filter(
            classe=inscription.classe
        ).select_related('matiere', 'enseignant').order_by('jour', 'heure_debut')

    jours_labels = {
        'lundi': 'Lundi', 'mardi': 'Mardi', 'mercredi': 'Mercredi',
        'jeudi': 'Jeudi', 'vendredi': 'Vendredi', 'samedi': 'Samedi',
    }
    # Regrouper par jour
    edt_par_jour = {}
    for jour, label in jours_labels.items():
        creneaux_jour = [c for c in creneaux if c.jour == jour]
        if creneaux_jour:
            edt_par_jour[label] = creneaux_jour

    return render(request, 'core/famille/emploi_du_temps.html', {
        'eleve': eleve,
        'inscription': inscription,
        'edt_par_jour': edt_par_jour,
        'creneaux': creneaux,
    })

# ── COTE ADMINISTRATION : traiter les reclamations ───────────

@login_required
def liste_reclamations_admin(request):
    if not (request.user.is_admin or request.user.is_secretariat):
        messages.error(request, "Acces reserve aux administrateurs.")
        return redirect('dashboard')
    etab = request.etablissement
    reclamations = Reclamation.objects.filter(eleve__etablissement=etab).select_related(
        'eleve', 'note_periode__matiere', 'note_periode__periode', 'auteur'
    )
    statut_filtre = request.GET.get('statut', '')
    if statut_filtre:
        reclamations = reclamations.filter(statut=statut_filtre)
    nb_attente = Reclamation.objects.filter(eleve__etablissement=etab, statut='en_attente').count()
    return render(request, 'core/famille/admin_liste_reclamations.html', {
        'reclamations': reclamations, 'statut_filtre': statut_filtre, 'nb_attente': nb_attente,
        'statuts': Reclamation.STATUTS,
    })


@login_required
def traiter_reclamation(request, pk):
    if not request.user.is_admin:
        return redirect('dashboard')
    etab = request.etablissement
    reclamation = get_object_or_404(Reclamation, pk=pk, eleve__etablissement=etab)
    if request.method == 'POST':
        from django.utils import timezone
        reclamation.statut = request.POST.get('statut', reclamation.statut)
        reclamation.reponse = request.POST.get('reponse', '').strip()
        reclamation.traite_par = request.user
        reclamation.date_traitement = timezone.now()
        reclamation.save()
        
        # P3.4 : Notification parent lors de réponse à réclamation
        # Fix: statuts réels du modèle = 'acceptee' / 'rejetee' (pas 'traite'/'rejete')
        # Fix: on utilise core.Notification (conçu pour notifier un utilisateur)
        if reclamation.statut in ['acceptee', 'rejetee']:
            from core.models import Notification
            if reclamation.auteur:
                Notification.objects.create(
                    destinataire=reclamation.auteur,
                    type_notif=Notification.TYPE_SYSTEM,
                    titre=(
                        f"Réclamation {reclamation.get_statut_display().lower()} "
                        f"— {reclamation.note_periode.matiere.nom}"
                    ),
                    message=(
                        f"Votre réclamation a été examinée.\n"
                        f"Statut : {reclamation.get_statut_display()}.\n"
                        f"Réponse : {reclamation.reponse or 'Aucune réponse ajoutée.'}"
                    ),
                    lien=f"/espace/{reclamation.eleve.pk}/reclamations/",
                )
            
        messages.success(request, "Reclamation traitee.")
        return redirect('liste_reclamations_admin')
    return render(request, 'core/famille/admin_traiter_reclamation.html', {'reclamation': reclamation})


# ── MESSAGERIE FAMILLE ────────────────────────────────────────

@login_required
@require_famille
def espace_messages(request, eleve_pk):
    """Liste des messages envoyes par ce parent/eleve."""
    eleve = get_eleve_ou_403(request, eleve_pk)
    from notes.models import MessageFamille
    messages_list = MessageFamille.objects.filter(
        expediteur=request.user, eleve=eleve
    ).order_by('-date_envoi')
    return render(request, 'core/famille/messages.html', {
        'eleve': eleve, 'messages_list': messages_list,
    })


@login_required
@require_famille
def envoyer_message(request, eleve_pk):
    """Formulaire d'envoi d'un message vers l'administration."""
    eleve = get_eleve_ou_403(request, eleve_pk)
    etab = eleve.etablissement
    from notes.models import MessageFamille
    from accounts.models import User

    # Construire la liste des destinataires disponibles avec leur nom réel
    destinataires_disponibles = []
    for role_val, role_label in MessageFamille.DESTINATAIRES:
        if role_val == 'administration':
            destinataires_disponibles.append({
                'value': 'administration__',
                'label': '📢 Administration (tous)',
                'user_pk': None,
            })
        elif role_val == 'enseignant':
            # Lister les enseignants affectés à la classe de l'élève
            inscription = eleve.get_inscription_active()
            if inscription:
                from etablissements.models import AffectationMatiere, AnneeScolaire
                annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
                affs = AffectationMatiere.objects.filter(
                    classe=inscription.classe, annee=annee
                ).select_related('enseignant__user', 'matiere').distinct()
                for aff in affs:
                    destinataires_disponibles.append({
                        'value': f'enseignant__{aff.enseignant.user.pk}',
                        'label': f'👩‍🏫 {aff.enseignant.nom_complet} ({aff.matiere.nom})',
                        'user_pk': aff.enseignant.user.pk,
                    })
        else:
            # Directeur, Comptable, Surveillant — chercher le compte réel
            user = User.objects.filter(etablissement=etab, role=role_val, is_active=True).first()
            if user:
                icons = {'directeur': '🏫', 'comptable': '💳', 'surveillant': '👮'}
                destinataires_disponibles.append({
                    'value': f'{role_val}__{user.pk}',
                    'label': f"{icons.get(role_val,'👤')} {role_label} — {user.get_full_name()}",
                    'user_pk': user.pk,
                })
            else:
                destinataires_disponibles.append({
                    'value': f'{role_val}__',
                    'label': f'👤 {role_label}',
                    'user_pk': None,
                })

    if request.method == 'POST':
        sujet = request.POST.get('sujet', '').strip()
        corps = request.POST.get('corps', '').strip()
        dest_value = request.POST.get('destinataire', '')

        if not sujet or not corps or not dest_value:
            messages.error(request, "Remplissez tous les champs.")
        else:
            # Décoder le destinataire
            parts = dest_value.split('__', 1)
            role_dest = parts[0]
            user_pk = parts[1] if len(parts) > 1 and parts[1] else None
            dest_user = None
            if user_pk:
                try:
                    dest_user = User.objects.get(pk=int(user_pk))
                except (User.DoesNotExist, ValueError):
                    pass

            MessageFamille.objects.create(
                etablissement=etab,
                expediteur=request.user,
                eleve=eleve,
                destinataire_role=role_dest,
                destinataire_user=dest_user,
                sujet=sujet,
                corps=corps,
                statut='non_lu',
            )
            messages.success(request, "Message envoye avec succes.")
            return redirect('espace_messages', eleve_pk=eleve.pk)

    return render(request, 'core/famille/form_message.html', {
        'eleve': eleve,
        'destinataires': destinataires_disponibles,
    })


# ── ADMIN : voir et repondre aux messages ─────────────────────

@login_required
def admin_messages(request):
    """Liste des messages recus par l'administration, filtrée selon le rôle."""
    if not (request.user.is_admin or request.user.is_surveillant or request.user.is_comptable or request.user.is_secretariat):
        return redirect('dashboard')

    from notes.models import MessageFamille
    from django.db.models import Q

    etab = request.etablissement

    # Construire le queryset de base selon le rôle de l'utilisateur connecté.
    # L'admin voit tous les messages de l'établissement.
    # Les autres rôles (surveillant, comptable) ne voient que les messages
    # qui leur sont adressés directement ou diffusés à toute l'administration.
    if request.user.is_admin:
        msgs = MessageFamille.objects.filter(etablissement=etab)
    else:
        msgs = MessageFamille.objects.filter(etablissement=etab).filter(
            Q(destinataire_user=request.user) |
            Q(destinataire_role='administration')
        )

    # Appliquer l'ordre et le filtre de statut sur le queryset restreint
    msgs = msgs.order_by('-date_envoi')
    nb_non_lus = msgs.filter(statut='non_lu').count()

    statut_filtre = request.GET.get('statut', '')
    if statut_filtre:
        msgs = msgs.filter(statut=statut_filtre)

    return render(request, 'core/famille/admin_messages.html', {
        'messages_list': msgs, 'nb_non_lus': nb_non_lus,
        'statuts': MessageFamille.STATUTS, 'statut_filtre': statut_filtre,
    })


@login_required
def admin_repondre_message(request, pk):
    """Lire et repondre a un message."""
    from notes.models import MessageFamille
    from django.utils import timezone
    etab = request.etablissement
    msg = get_object_or_404(MessageFamille, pk=pk, etablissement=etab)

    # Marquer comme lu
    if msg.statut == 'non_lu':
        msg.statut = 'lu'
        msg.save()

    if request.method == 'POST':
        reponse = request.POST.get('reponse', '').strip()
        if reponse:
            msg.reponse = reponse
            msg.repondu_par = request.user
            msg.date_reponse = timezone.now()
            msg.statut = 'repondu'
            msg.save()
            messages.success(request, "Reponse envoyee.")
            return redirect('admin_messages')

    return render(request, 'core/famille/admin_repondre_message.html', {'msg': msg})
