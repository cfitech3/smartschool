"""
Vue SaaS pour le super admin uniquement.
Tableau de bord réseau : stats commerciales, logs d'intervention, santé des établissements.
"""
import datetime
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q, Max
from django.utils import timezone
from .models import Etablissement, AnneeScolaire
from accounts.models import User
from eleves.models import Eleve
from finances.models import Paiement
from notes.models import LogModificationNote


def superadmin_required(fn):
    def w(request, *a, **k):
        if not request.user.is_authenticated or request.user.role != 'super_admin':
            return redirect('dashboard')
        return fn(request, *a, **k)
    w.__name__ = fn.__name__
    return w


@login_required
@superadmin_required
def dashboard_saas(request):
    """
    Vue réseau super admin : santé SaaS, statistiques commerciales,
    établissements actifs/inactifs, dernières interventions.
    """
    today = timezone.now().date()

    etabs = Etablissement.objects.all().order_by('nom').annotate(
        nb_eleves=Count('eleves', filter=Q(eleves__is_active=True)),
        nb_users=Count('utilisateurs', filter=Q(utilisateurs__is_active=True)),
        derniere_activite=Max('utilisateurs__last_login'),
    )

    # ── Stats réseau ────────────────────────────────────────────────────────
    stats = {
        'nb_etabs_actifs':   etabs.filter(is_active=True).count(),
        'nb_etabs_suspendus': etabs.filter(is_active=False).count(),
        'nb_eleves_total':   Eleve.objects.filter(is_active=True).count(),
        'nb_users_total':    User.objects.filter(is_active=True).exclude(role='super_admin').count(),
        'recettes_reseau_mois': float(Paiement.objects.filter(
            statut='valide',
            date_paiement__month=today.month,
            date_paiement__year=today.year,
        ).aggregate(t=Sum('montant'))['t'] or 0),
        'recettes_reseau_annee': float(Paiement.objects.filter(
            statut='valide',
            date_paiement__year=today.year,
        ).aggregate(t=Sum('montant'))['t'] or 0),
    }

    # ── Recettes et activité par établissement ────────────────────────────────
    import json
    for e in etabs:
        e.recettes_mois = float(Paiement.objects.filter(
            etablissement=e, statut='valide',
            date_paiement__month=today.month,
            date_paiement__year=today.year,
        ).aggregate(t=Sum('montant'))['t'] or 0)
        e.recettes_annee = float(Paiement.objects.filter(
            etablissement=e, statut='valide',
            date_paiement__year=today.year,
        ).aggregate(t=Sum('montant'))['t'] or 0)
        semaine_debut = timezone.now() - datetime.timedelta(days=7)
        e.connexions_semaine = User.objects.filter(
            etablissement=e,
            last_login__gte=semaine_debut
        ).count()
        # Santé : score basé sur activité
        e.sante = 'active' if e.connexions_semaine > 0 and e.is_active else (
            'inactive' if e.is_active else 'suspendue'
        )

    # ── Croissance mensuelle (12 mois) pour le graphique ────────────────────
    chart_croissance = []
    for i in range(11, -1, -1):
        d = today.replace(day=1) - datetime.timedelta(days=i*28)
        nb = Eleve.objects.filter(
            date_inscription__month=d.month if hasattr(d, 'month') else today.month,
            date_inscription__year=d.year if hasattr(d, 'year') else today.year,
            is_active=True,
        ).count() if hasattr(Eleve, 'date_inscription') else 0
        recettes = float(Paiement.objects.filter(
            statut='valide',
            date_paiement__month=d.month,
            date_paiement__year=d.year,
        ).aggregate(t=Sum('montant'))['t'] or 0)
        chart_croissance.append({
            'mois': d.strftime('%b %Y'),
            'recettes': recettes,
        })

    # ── Journal d'interventions (logs récents super admin) ────────────────────
    logs_recents = LogModificationNote.objects.select_related(
        'note_periode__eleve__etablissement', 'modifie_par'
    ).order_by('-date_modif')[:15]

    # ── Établissements sans activité récente (> 7 jours) ─────────────────────
    etabs_inactifs_warn = [
        e for e in etabs
        if e.is_active and e.nb_eleves > 0 and e.connexions_semaine == 0
    ]

    # ── Comptes récemment créés sur tout le réseau ────────────────────────────
    derniers_users = User.objects.exclude(role='super_admin').select_related(
        'etablissement'
    ).order_by('-date_creation')[:10]

    return render(request, 'etablissements/superadmin/dashboard_saas.html', {
        'stats': stats,
        'etabs': etabs,
        'etabs_inactifs_warn': etabs_inactifs_warn,
        'chart_croissance': json.dumps(chart_croissance),
        'logs_recents': logs_recents,
        'derniers_users': derniers_users,
        'today': today,
    })
