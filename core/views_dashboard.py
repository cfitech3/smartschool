"""
Dashboards adaptés par rôle — SmartSchool v2.6
Chaque rôle reçoit uniquement les données pertinentes.
"""
import logging
import datetime
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Q
from django.utils import timezone
from eleves.models import Eleve, Presence, Inscription
from core.cycle_filter import get_cycles_actifs_ids, get_classes_actives, get_eleves_actifs, get_inscriptions_actives
from finances.models import Paiement
from etablissements.models import Etablissement, Classe, AnneeScolaire
from accounts.models import User
from notes.models import LogModificationNote, NotePeriode, EmploiDuTemps
from core.views_alertes import get_alertes_etablissement

logger = logging.getLogger(__name__)


@login_required
def dashboard(request):
    # Famille → espace famille
    if request.user.is_parent or request.user.is_eleve_user:
        return redirect('espace_accueil')

    role  = request.user.role
    etab  = request.etablissement
    today = timezone.now().date()

    # ── SUPER ADMIN ──────────────────────────────────────────
    if role == 'super_admin':
        return _dashboard_super_admin(request, today)

    if not etab:
        return render(request, 'core/dashboard_vide.html', {})

    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()

    # ── DIRECTEUR / ADMIN ────────────────────────────────────
    if role == 'admin':
        return _dashboard_admin(request, etab, annee, today)

    # ── SECRÉTARIAT ──────────────────────────────────────────
    if role == 'secretariat':
        return _dashboard_secretariat(request, etab, annee, today)

    # ── COMPTABLE ────────────────────────────────────────────
    if role == 'comptable':
        return _dashboard_comptable(request, etab, today)

    # ── ENSEIGNANT ───────────────────────────────────────────
    if role == 'enseignant':
        return _dashboard_enseignant(request, etab, annee, today)

    # ── SURVEILLANT ──────────────────────────────────────────
    if role == 'surveillant':
        return _dashboard_surveillant(request, etab, annee, today)

    # Fallback
    return render(request, 'core/dashboard.html', {'today': today})


# ══════════════════════════════════════════════════════════════
def _dashboard_super_admin(request, today):
    etabs = Etablissement.objects.all().order_by('nom').annotate(
        nb_eleves=Count('eleves', filter=Q(eleves__is_active=True)),
        nb_users=Count('utilisateurs', filter=Q(utilisateurs__is_active=True)),
    )
    stats = {
        'total_etablissements': etabs.filter(is_active=True).count(),
        'inactifs': etabs.filter(is_active=False).count(),
        'total_eleves': Eleve.objects.filter(is_active=True).count(),
        'total_users': User.objects.filter(is_active=True).exclude(role__in=['parent','eleve','super_admin']).count(),
        'total_parents': User.objects.filter(is_active=True, role='parent').count(),
        'recettes_mois': float(Paiement.objects.filter(
            statut='valide', date_paiement__month=today.month,
            date_paiement__year=today.year
        ).aggregate(t=Sum('montant'))['t'] or 0),
    }

    # Fix PERF-001 : remplace la boucle N+1 par 2 requêtes bulk
    etabs_ids = list(etabs.values_list('pk', flat=True))

    recettes_raw = (
        Paiement.objects
        .filter(
            etablissement_id__in=etabs_ids, statut='valide',
            date_paiement__month=today.month, date_paiement__year=today.year,
        )
        .values('etablissement_id')
        .annotate(t=Sum('montant'))
    )
    recettes_map = {r['etablissement_id']: float(r['t'] or 0) for r in recettes_raw}

    paiements_raw = (
        Paiement.objects
        .filter(
            etablissement_id__in=etabs_ids, statut='valide',
            date_paiement__date=today,
        )
        .values('etablissement_id')
        .annotate(nb=Count('pk'))
    )
    paiements_map = {r['etablissement_id']: r['nb'] for r in paiements_raw}

    for e in etabs:
        e.recettes_mois = recettes_map.get(e.pk, 0.0)
        e.nb_paiements_jour = paiements_map.get(e.pk, 0)

    derniers_users = User.objects.exclude(role='super_admin').select_related('etablissement').order_by('-date_creation')[:8]
    return render(request, 'core/dashboard_super.html', {
        'stats': stats, 'etablissements': etabs,
        'derniers_users': derniers_users, 'today': today,
    })


# ══════════════════════════════════════════════════════════════
def _dashboard_admin(request, etab, annee, today):
    import json
    stats = {}
    stats['total_eleves']     = get_eleves_actifs(etab, annee).count()  # Fix: filtre par année active
    stats['total_enseignants']= User.objects.filter(etablissement=etab, role='enseignant', is_active=True).count()
    stats['total_classes']    = get_classes_actives(etab, annee).count() if annee else 0
    stats['total_staff']      = User.objects.filter(etablissement=etab, is_active=True).exclude(
        role__in=['parent', 'eleve', 'admin', 'super_admin']
    ).count()

    # Présences aujourd'hui (cycles actifs uniquement)
    cycles_ids = get_cycles_actifs_ids(etab)
    stats['presents_today'] = Presence.objects.filter(classe__etablissement=etab, classe__niveau__cycle__in=cycles_ids, date=today, statut='present').count()
    stats['absents_today']  = Presence.objects.filter(classe__etablissement=etab, classe__niveau__cycle__in=cycles_ids, date=today, statut='absent').count()

    # Finances — Fix: utilise les élèves actifs de l'année au lieu de jointure fragile
    eleves_actifs_ids = get_eleves_actifs(etab, annee).values_list('pk', flat=True)

    pay_today = Paiement.objects.filter(
        etablissement=etab, date_paiement__date=today,
        statut='valide', eleve_id__in=eleves_actifs_ids,
    )
    stats['paiements_jour']    = float(pay_today.aggregate(t=Sum('montant'))['t'] or 0)
    stats['nb_paiements_jour'] = pay_today.count()

    recettes_qs = Paiement.objects.filter(
        etablissement=etab, statut='valide',
        date_paiement__month=today.month, date_paiement__year=today.year,
        eleve_id__in=eleves_actifs_ids,
    )
    stats['recettes_mois'] = float(recettes_qs.aggregate(t=Sum('montant'))['t'] or 0)

    eleves_payes_ids = recettes_qs.values_list('eleve_id', flat=True).distinct()
    
    from finances.models import Echeance
    stats['eleves_retard'] = Echeance.objects.filter(
        etablissement=etab, annee=annee, statut__in=['a_payer', 'retard'], date_limite__lt=today
    ).values('eleve_id').distinct().count()

    # Notifications
    stats['notifs_non_lues'] = LogModificationNote.objects.filter(
        note_periode__eleve__etablissement=etab, notif_lue=False
    ).count()
    stats['nb_reclamations'] = 0
    try:
        from notes.models import Reclamation
        stats['nb_reclamations'] = Reclamation.objects.filter(
            eleve__etablissement=etab, statut='en_attente'
        ).count()
    except ImportError:
        logger.warning("Modèle Reclamation non disponible")
    except Exception:
        logger.exception("Erreur comptage réclamations admin")
    stats['nb_messages'] = 0
    try:
        from notes.models import MessageFamille
        stats['nb_messages'] = MessageFamille.objects.filter(
            destinataire_role='directeur', statut='non_lu',
            expediteur__etablissement=etab
        ).count()
    except ImportError:
        logger.warning("Modèle MessageFamille non disponible")
    except Exception:
        logger.exception("Erreur comptage messages admin")

    # Graphique 30 jours (couvre mieux les données réelles)
    chart = []
    for i in range(29, -1, -1):
        d = today - datetime.timedelta(days=i)
        total = float(Paiement.objects.filter(
            etablissement=etab, date_paiement__date=d, statut='valide'
        ).aggregate(t=Sum('montant'))['t'] or 0)
        chart.append({'jour': d.strftime('%d/%m'), 'total': total})

    paiements_recent = Paiement.objects.filter(
        etablissement=etab, statut='valide'
    ).select_related('eleve','type_frais').order_by('-date_paiement')[:6]

    classes_data = []
    if annee:
        classes_data = get_classes_actives(etab, annee).annotate(
            nb=Count('inscriptions', filter=Q(inscriptions__is_active=True))
        ).order_by('niveau__ordre', 'nom')[:8]

    # Élèves récemment inscrits
    inscrits_recents = get_inscriptions_actives(etab, annee).select_related('eleve','classe').order_by('-date_inscription')[:5] if annee else []

    alertes = get_alertes_etablissement(etab, annee, request.user.role)
    return render(request, 'core/dashboard_admin.html', {
        'stats': stats, 'paiements_recent': paiements_recent,
        'classes_data': classes_data, 'chart_paiements': json.dumps(chart),
        'inscrits_recents': inscrits_recents, 'today': today, 'annee': annee,
        'alertes': alertes,
    })


# ══════════════════════════════════════════════════════════════
def _dashboard_secretariat(request, etab, annee, today):
    from core.cycle_filter import get_cycles_actifs_ids, get_eleves_actifs, get_classes_actives, get_inscriptions_actives
    cycles_ids = get_cycles_actifs_ids(etab)
    stats = {}
    stats['total_eleves']  = get_eleves_actifs(etab, annee).count()  # Fix: filtre par année active
    stats['total_classes'] = get_classes_actives(etab, annee).count() if annee else 0
    stats['presents_today'] = Presence.objects.filter(classe__etablissement=etab, classe__niveau__cycle__in=cycles_ids, date=today, statut='present').count()
    stats['absents_today']  = Presence.objects.filter(classe__etablissement=etab, classe__niveau__cycle__in=cycles_ids, date=today, statut='absent').count()
    stats['retards_today']  = Presence.objects.filter(classe__etablissement=etab, classe__niveau__cycle__in=cycles_ids, date=today, statut='retard').count()

    # Inscriptions récentes
    inscrits_recents = get_inscriptions_actives(etab, annee).select_related('eleve','classe').order_by('-date_inscription')[:8] if annee else []

    stats['nb_reclamations'] = 0
    stats['nb_messages'] = 0
    try:
        from notes.models import Reclamation, MessageFamille
        stats['nb_reclamations'] = Reclamation.objects.filter(
            eleve__etablissement=etab, statut='en_attente'
        ).count()
        stats['nb_messages'] = MessageFamille.objects.filter(
            expediteur__etablissement=etab, statut='non_lu'
        ).count()
    except ImportError:
        logger.warning("Modèles Reclamation/MessageFamille non disponibles (secrétariat)")
    except Exception:
        logger.exception("Erreur comptage notifications secrétariat")

    # Classes avec appel non fait aujourd'hui
    classes_sans_appel = []
    if annee:
        toutes_classes = Classe.objects.filter(etablissement=etab, annee=annee)
        classes_avec_appel = Presence.objects.filter(
            classe__etablissement=etab, date=today
        ).values_list('classe_id', flat=True).distinct()
        classes_sans_appel = toutes_classes.exclude(pk__in=classes_avec_appel)[:5]

    alertes = get_alertes_etablissement(etab, annee, request.user.role)
    return render(request, 'core/dashboard_secretariat.html', {
        'stats': stats, 'inscrits_recents': inscrits_recents,
        'classes_sans_appel': classes_sans_appel, 'today': today, 'annee': annee,
        'alertes': alertes,
    })


# ══════════════════════════════════════════════════════════════
def _dashboard_comptable(request, etab, today):
    import json
    from core.cycle_filter import get_eleves_actifs
    from etablissements.models import AnneeScolaire

    # Fix: recupere l'annee active pour avoir une definition coherente des eleves
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
    eleves_actifs_ids = list(get_eleves_actifs(etab, annee).values_list('pk', flat=True))

    # Fix: utilise eleve_id__in au lieu de la jointure fragile sur inscriptions
    base_pai = Paiement.objects.filter(
        etablissement=etab, statut='valide',
        eleve_id__in=eleves_actifs_ids,
    )
    stats = {}
    stats['recettes_jour']     = float(base_pai.filter(date_paiement__date=today).aggregate(t=Sum('montant'))['t'] or 0)
    stats['nb_paiements_jour'] = base_pai.filter(date_paiement__date=today).count()
    stats['recettes_mois']     = float(base_pai.filter(
        date_paiement__month=today.month, date_paiement__year=today.year
    ).aggregate(t=Sum('montant'))['t'] or 0)
    stats['total_eleves'] = len(eleves_actifs_ids)  # deja calcule, pas de 2eme requete

    recettes_mois_qs = base_pai.filter(
        date_paiement__month=today.month, date_paiement__year=today.year
    )
    eleves_payes_ids = recettes_mois_qs.values_list('eleve_id', flat=True).distinct()
    stats['eleves_payes'] = eleves_payes_ids.count()

    # Fix: Calcul exact basé sur les échéances (Tranches) en retard
    from finances.models import Echeance
    stats['eleves_retard'] = Echeance.objects.filter(
        etablissement=etab, annee=annee, statut__in=['a_payer', 'retard'], date_limite__lt=today
    ).values('eleve_id').distinct().count()
    stats['taux_recouvrement'] = round(
        stats['eleves_payes'] / stats['total_eleves'] * 100, 1
    ) if stats['total_eleves'] > 0 else 0


    # Graphique 30 jours
    chart = []
    for i in range(29, -1, -1):
        d = today - datetime.timedelta(days=i)
        total = float(Paiement.objects.filter(
            etablissement=etab, date_paiement__date=d, statut='valide'
        ).aggregate(t=Sum('montant'))['t'] or 0)
        chart.append({'jour': d.strftime('%d/%m'), 'total': total})

    paiements_recent = Paiement.objects.filter(
        etablissement=etab, statut='valide'
    ).select_related('eleve','type_frais').order_by('-date_paiement')[:10]

    # Répartition par type de frais
    from finances.models import TypeFrais
    repartition = Paiement.objects.filter(
        etablissement=etab, statut='valide',
        date_paiement__month=today.month, date_paiement__year=today.year
    ).values('type_frais__nom').annotate(total=Sum('montant')).order_by('-total')

    alertes = get_alertes_etablissement(etab, None, request.user.role)
    return render(request, 'core/dashboard_comptable.html', {
        'stats': stats, 'paiements_recent': paiements_recent,
        'chart_paiements': json.dumps(chart), 'repartition': list(repartition),
        'today': today, 'alertes': alertes,
    })


# ══════════════════════════════════════════════════════════════
def _dashboard_enseignant(request, etab, annee, today):
    user = request.user
    # Classes où ce prof enseigne (via EmploiDuTemps)
    edt_prof = EmploiDuTemps.objects.filter(
        enseignant=user, classe__etablissement=etab
    ).select_related('classe', 'matiere', 'classe__niveau')
    if annee:
        edt_prof = edt_prof.filter(classe__annee=annee)

    # Reconstruire les "affectations" depuis l'EDT (classe + matière uniques)
    from django.db.models import Count as DjCount
    affectations_qs = edt_prof.values('classe__id','classe__nom','classe__niveau__nom','matiere__id','matiere__nom','matiere__coefficient').distinct()
    # Construire une liste simple pour le template
    affectations = list(affectations_qs)
    classes_ids  = list(set(a['classe__id'] for a in affectations))

    stats = {}
    stats['nb_classes']   = len(classes_ids)
    stats['nb_matieres']  = len(set(a['matiere__id'] for a in affectations))
    stats['nb_eleves']    = Inscription.objects.filter(
        classe__in=classes_ids, is_active=True
    ).values('eleve_id').distinct().count() if classes_ids else 0  # Fix: élèves uniques

    # Notes saisies vs à saisir
    periode = None
    from notes.models import Periode
    periode = Periode.objects.filter(etablissement=etab, is_active=True).first()
    stats['notes_saisies'] = NotePeriode.objects.filter(
        saisi_par=user, periode=periode
    ).count() if periode else 0

    # Emploi du temps de ce prof aujourd'hui
    jour_map = {0:'lundi',1:'mardi',2:'mercredi',3:'jeudi',4:'vendredi',5:'samedi',6:'dimanche'}
    jour_auj = jour_map.get(today.weekday(), '')
    cours_auj = EmploiDuTemps.objects.filter(
        enseignant=user, jour=jour_auj
    ).select_related('classe','matiere').order_by('heure_debut') if jour_auj else []

    # EDT de la semaine
    edt_semaine = EmploiDuTemps.objects.filter(
        enseignant=user
    ).select_related('classe','matiere').order_by('jour','heure_debut')

    return render(request, 'core/dashboard_enseignant.html', {
        'stats': stats, 'affectations': affectations,
        'cours_auj': cours_auj, 'edt_semaine': edt_semaine,
        'periode': periode, 'today': today, 'jour_auj': jour_auj,
    })


# ══════════════════════════════════════════════════════════════
def _dashboard_surveillant(request, etab, annee, today):
    from core.cycle_filter import get_cycles_actifs_ids, get_eleves_actifs, get_classes_actives
    cycles_ids = get_cycles_actifs_ids(etab)
    stats = {}
    stats['presents_today'] = Presence.objects.filter(
        classe__etablissement=etab, classe__niveau__cycle__in=cycles_ids, date=today, statut='present'
    ).count()
    stats['absents_today']  = Presence.objects.filter(
        classe__etablissement=etab, classe__niveau__cycle__in=cycles_ids, date=today, statut='absent'
    ).count()
    stats['retards_today']  = Presence.objects.filter(
        classe__etablissement=etab, classe__niveau__cycle__in=cycles_ids, date=today, statut='retard'
    ).count()
    stats['total_classes']  = get_classes_actives(etab, annee).count() if annee else 0
    stats['total_eleves']   = get_eleves_actifs(etab, annee).count()  # Fix: filtre par année active

    # Taux de présence
    total_presence = stats['presents_today'] + stats['absents_today'] + stats['retards_today']
    stats['taux_presence'] = round(stats['presents_today'] / total_presence * 100, 1) if total_presence > 0 else 0

    # Classes sans appel aujourd'hui
    if annee:
        toutes = get_classes_actives(etab, annee)
        avec_appel = Presence.objects.filter(
            classe__etablissement=etab, date=today
        ).values_list('classe_id', flat=True).distinct()
        classes_sans_appel = toutes.exclude(pk__in=avec_appel)
    else:
        classes_sans_appel = []

    # Absences récurrentes (plus de 3 absences ce mois)
    debut_mois = today.replace(day=1)
    absents_freq = Presence.objects.filter(
        classe__etablissement=etab, date__gte=debut_mois, statut='absent'
    ).values('eleve__nom', 'eleve__prenom', 'eleve__pk').annotate(
        nb=Count('pk')
    ).filter(nb__gte=3).order_by('-nb')[:8]

    # EDT du jour pour toutes les classes
    jour_map = {0:'lundi',1:'mardi',2:'mercredi',3:'jeudi',4:'vendredi',5:'samedi'}
    jour_auj = jour_map.get(today.weekday(), '')
    edt_auj = EmploiDuTemps.objects.filter(
        classe__etablissement=etab, jour=jour_auj
    ).select_related('classe','matiere','enseignant').order_by(
        'classe__nom','heure_debut'
    ) if jour_auj else []

    return render(request, 'core/dashboard_surveillant.html', {
        'stats': stats, 'classes_sans_appel': classes_sans_appel,
        'absents_freq': absents_freq, 'edt_auj': edt_auj,
        'today': today, 'jour_auj': jour_auj,
    })
