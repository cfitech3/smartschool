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
    periodes = Periode.objects.filter(etablissement=etab, annee=annee) if annee else Periode.objects.none()
    periode_active = periodes.filter(is_active=True).first()
    inscription = eleve.get_inscription_active()
    cycle = inscription.classe.niveau.cycle if (inscription and inscription.classe.niveau and inscription.classe.niveau.cycle) else None

    # Resume notes (periode active ou LMD)
    moy_generale = None
    if cycle and cycle.type_cycle == 'universite' and annee:
        from notes.models import NoteUE
        notes_ue = NoteUE.objects.filter(eleve=eleve, periode__annee=annee).select_related('ue')
        total_pts = 0.0
        total_cred = 0
        for n in notes_ue:
            if n.note_retenue is not None:
                c = n.ue.credits or 1
                total_pts += float(n.note_retenue) * c
                total_cred += c
        if total_cred > 0:
            moy_generale = round(total_pts / total_cred, 2)
    elif periode_active:
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
    
    inscription = eleve.get_inscription_active()
    cycle = None
    is_premier_cycle = False
    is_universite = False
    if inscription and inscription.classe.niveau and inscription.classe.niveau.cycle:
        cycle = inscription.classe.niveau.cycle
        is_premier_cycle = cycle.is_premier_cycle and cycle.utilise_compositions_multiples
        is_universite = (cycle.type_cycle == 'universite')

    if is_universite:
        from notes.models import NoteUE
        notes_ue = NoteUE.objects.filter(
            eleve=eleve, periode__annee=annee
        ).select_related('ue').order_by('ue__semestre', 'ue__code') if annee else []
        lignes = []
        total_pts = 0.0
        total_cred = 0
        for n in notes_ue:
            cred = n.ue.credits or 1
            moy_ue = n.note_retenue
            if moy_ue is not None:
                total_pts += float(moy_ue) * cred
                total_cred += cred
            lignes.append({
                'matiere': type('UEMat', (), {'nom': f"{n.ue.code} — {n.ue.nom}", 'coefficient': cred, 'is_conduite': False})(),
                'note_classe': n.note,
                'note_compo': n.note_rattrapage,
                'moyenne_finale': moy_ue,
                'coefficient': cred,
                'appreciation': n.mention if moy_ue is not None else '—',
                'note_id': None,
                'a_reclamation': False,
            })
        moy_gen = round(total_pts / total_cred, 2) if total_cred > 0 else None
        return render(request, 'core/famille/notes.html', {
            'eleve': eleve, 'periodes': Periode.objects.none(), 'periode': None,
            'lignes': lignes, 'moy_generale': moy_gen, 'is_premier_cycle': False, 'is_universite': True,
        })
    elif is_premier_cycle:
        nb_compos = cycle.nb_compositions_trimestre if cycle else 3
        numeros = list(range(1, nb_compos + 1))
        try:
            numero = int(request.GET.get('numero', 1))
        except ValueError:
            numero = 1

        lignes, moy_gen = [], None
        if annee:
            from notes.services import calculer_bulletin_composition
            matieres = Matiere.objects.filter(etablissement=etab)
            lignes, moy_gen, _, _ = calculer_bulletin_composition(eleve, annee, numero, matieres)
            
            # Adaptation pour le template notes.html
            for l in lignes:
                l['note_id'] = None
                l['a_reclamation'] = False
                l['moyenne_finale'] = l['note']
            
        return render(request, 'core/famille/notes.html', {
            'eleve': eleve, 'annee': annee, 'numeros': numeros, 'numero': numero,
            'lignes': lignes, 'moy_generale': moy_gen, 'is_premier_cycle': True
        })
    else:
        periodes = Periode.objects.filter(etablissement=etab, annee=annee) if annee else Periode.objects.none()
        periode_id = request.GET.get('periode')
        periode = get_object_or_404(Periode, pk=periode_id, etablissement=etab) if periode_id else periodes.filter(is_active=True).first()

        lignes, moy_gen = [], None
        if periode:
            matieres = Matiere.objects.filter(etablissement=etab)
            lignes, moy_gen, _, _ = calculer_bulletin(eleve, periode, matieres)
            for l in lignes:
                note_obj = NotePeriode.objects.filter(eleve=eleve, matiere=l['matiere'], periode=periode).first()
                l['note_id'] = note_obj.pk if note_obj else None
                l['a_reclamation'] = Reclamation.objects.filter(note_periode=note_obj).exists() if note_obj else False

        return render(request, 'core/famille/notes.html', {
            'eleve': eleve, 'periodes': periodes, 'periode': periode,
            'lignes': lignes, 'moy_generale': moy_gen, 'is_premier_cycle': False
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
    
    inscription = eleve.get_inscription_active()
    is_premier_cycle = False
    is_universite = False
    if inscription and inscription.classe.niveau and inscription.classe.niveau.cycle:
        cycle = inscription.classe.niveau.cycle
        is_premier_cycle = cycle.is_premier_cycle and cycle.utilise_compositions_multiples
        is_universite = (cycle.type_cycle == 'universite')

    if is_universite:
        from notes.views_universite import releve_notes_lmd
        etab = eleve.etablissement
        annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
        per = Periode.objects.filter(pk=periode_pk, etablissement=etab).first()
        if not per and annee:
            per = Periode.objects.filter(etablissement=etab, annee=annee, is_active=True).first() or Periode.objects.filter(etablissement=etab, annee=annee).first()
        if not per:
            messages.error(request, "Aucune période académique disponible pour générer le relevé LMD.")
            return redirect('espace_notes', eleve_pk=eleve.pk)
        return releve_notes_lmd(request, eleve_pk=eleve.pk, periode_pk=per.pk)
    elif is_premier_cycle:
        from notes.views_notes import bulletin_composition
        etab = eleve.etablissement
        annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
        if not annee:
            messages.error(request, "Aucune année scolaire active.")
            return redirect('espace_notes', eleve_pk=eleve.pk)
        # Le paramètre periode_pk fait office de numero pour le 1er cycle
        return bulletin_composition(request, eleve_pk=eleve.pk, annee_pk=annee.pk, numero=periode_pk)
    else:
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
    from django.db.models import Q
    from finances.models import Echeance, ReductionFrais
    from django.utils import timezone
    today = timezone.now().date()

    types_obligatoires = TypeFrais.objects.filter(etablissement=etab, is_obligatoire=True)
    if annee:
        types_obligatoires = types_obligatoires.filter(Q(annee=annee) | Q(annee__isnull=True))
    reductions_map = {
        r.type_frais_id: r.montant
        for r in ReductionFrais.objects.filter(eleve=eleve, annee=annee)
    } if annee else {}

    frais_attendus = []
    nb_retards = 0
    for tf in types_obligatoires:
        paye = paiements.filter(type_frais=tf).aggregate(t=Sum('montant'))['t'] or 0 if paiements else 0
        reduction = reductions_map.get(tf.pk, 0)
        attendu = max(0, tf.montant_defaut - reduction)
        reste_du = max(0, attendu - paye)
        
        # P3.3: Vérifier s'il y a de vraies tranches en retard pour ce type de frais
        echeances_retard = Echeance.objects.filter(
            eleve=eleve, annee=annee, type_frais=tf,
            statut__in=['a_payer', 'retard'], date_limite__lt=today
        ).count() if annee else 0
        
        en_retard = (echeances_retard > 0 and reste_du > 0)
        if en_retard:
            nb_retards += 1
            
        frais_attendus.append({
            'type': tf,
            'attendu': attendu,
            'paye': paye,
            'solde': reste_du,
            'en_retard': en_retard,
        })

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
                'label': ' Administration (tous)',
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
                        'label': f'‍ {aff.enseignant.nom_complet} ({aff.matiere.nom})',
                        'user_pk': aff.enseignant.user.pk,
                    })
        else:
            # Directeur (rôle 'admin' en base), Comptable, Surveillant — chercher le compte réel
            db_role = 'admin' if role_val == 'directeur' else role_val
            user = User.objects.filter(etablissement=etab, role=db_role, is_active=True).first()
            if user:
                icons = {'directeur': '', 'comptable': '', 'surveillant': ''}
                destinataires_disponibles.append({
                    'value': f'{role_val}__{user.pk}',
                    'label': f"{icons.get(role_val,'')} {role_label} — {user.get_full_name()}",
                    'user_pk': user.pk,
                })
            else:
                destinataires_disponibles.append({
                    'value': f'{role_val}__',
                    'label': f' {role_label}',
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
                    dest_user = User.objects.get(pk=int(user_pk), etablissement=etab)
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
    if not (request.user.is_admin or request.user.is_surveillant or request.user.is_comptable or request.user.is_secretariat or request.user.is_enseignant):
        return redirect('dashboard')

    from notes.models import MessageFamille
    from django.db.models import Q

    etab = request.etablissement

    # Construire le queryset de base selon le rôle de l'utilisateur connecté.
    # L'admin voit tous les messages de l'établissement.
    # Les autres rôles (surveillant, comptable, enseignant) ne voient que les messages
    # qui leur sont adressés directement ou diffusés à toute l'administration.
    if request.user.is_admin:
        msgs = MessageFamille.objects.filter(etablissement=etab)
    elif request.user.is_enseignant:
        msgs = MessageFamille.objects.filter(etablissement=etab, destinataire_user=request.user)
    else:
        msgs = MessageFamille.objects.filter(etablissement=etab).filter(
            Q(destinataire_user=request.user) |
            Q(destinataire_role='administration') |
            Q(destinataire_role=request.user.role)
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
    if not (request.user.is_admin or request.user.is_surveillant or request.user.is_comptable or request.user.is_secretariat or request.user.is_enseignant):
        messages.error(request, "Accès réservé au personnel de l'établissement.")
        return redirect('dashboard')

    from notes.models import MessageFamille
    from django.db.models import Q
    from django.utils import timezone
    etab = request.etablissement
    if request.user.is_admin:
        msg = get_object_or_404(MessageFamille, pk=pk, etablissement=etab)
    else:
        msg = get_object_or_404(
            MessageFamille.objects.filter(etablissement=etab).filter(
                Q(destinataire_user=request.user) | Q(destinataire_role='administration')
            ),
            pk=pk,
        )

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
            
            # --- Alerte Connectée (Interne + WhatsApp) ---
            if msg.expediteur:
                from core.models import Notification
                from core.whatsapp import send_whatsapp_message
                
                # 1. Notification Interne
                lien_notif = f"/espace/{msg.eleve_id}/messages/" if msg.eleve_id else "/espace/"
                Notification.objects.create(
                    destinataire=msg.expediteur,
                    type_notif=Notification.TYPE_MESSAGE,
                    titre="Nouvelle réponse de l'administration",
                    message=f"L'administration a répondu à votre message : '{msg.sujet}'",
                    lien=lien_notif
                )
                
                # 2. Notification WhatsApp (si le parent a un numéro)
                # L'expediteur du message (User) est le parent, on cherche son profil Tuteur
                if hasattr(msg.expediteur, 'profil_tuteur') and msg.expediteur.profil_tuteur:
                    telephone = msg.expediteur.profil_tuteur.telephone
                    if telephone:
                        texte_wa = (
                            f" *{etab.nom}*\n\n"
                            f"Bonjour {msg.expediteur.first_name},\n"
                            f"La direction a répondu à votre message concernant : *{msg.sujet}*.\n\n"
                            f" Connectez-vous sur votre application SmartSchool pour lire la réponse."
                        )
                        send_whatsapp_message(telephone, texte_wa)

            messages.success(request, "Reponse envoyee et parent notifié.")
            return redirect('admin_messages')

    return render(request, 'core/famille/admin_repondre_message.html', {'msg': msg})
