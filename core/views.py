from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Q
from django.utils import timezone
from django.core.cache import cache
from eleves.models import Eleve, Presence
from finances.models import Paiement
from etablissements.models import Etablissement, Classe, AnneeScolaire
from accounts.models import User
from notes.models import LogModificationNote
import json, datetime
from core.cycle_filter import get_cycles_actifs_ids, get_classes_actives, get_eleves_actifs, get_inscriptions_actives


@login_required
def dashboard(request):
    if request.user.is_parent or request.user.is_eleve_user:
        return redirect('espace_accueil')
    etab = request.etablissement
    today = timezone.now().date()
    stats = {}
    paiements_recent = []
    classes_data = []
    chart_paiements = []

    if etab:
        annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
        cache_key = f'dashboard_{etab.pk}_{today}'
        cached = cache.get(cache_key)

        if not cached:
            stats['total_eleves'] = get_eleves_actifs(etab).count()
            stats['total_enseignants'] = User.objects.filter(etablissement=etab, role='enseignant', is_active=True).count()
            stats['total_classes'] = get_classes_actives(etab, annee).count() if annee else 0
            pay_today = Paiement.objects.filter(etablissement=etab, date_paiement__date=today, statut='valide')
            stats['paiements_jour'] = float(pay_today.aggregate(t=Sum('montant'))['t'] or 0)
            stats['nb_paiements_jour'] = pay_today.count()
            stats['recettes_mois'] = float(Paiement.objects.filter(
                etablissement=etab, date_paiement__month=today.month,
                date_paiement__year=today.year, statut='valide'
            ).aggregate(t=Sum('montant'))['t'] or 0)
            stats['presents_today'] = Presence.objects.filter(classe__etablissement=etab, date=today, statut='present').count()
            stats['absents_today'] = Presence.objects.filter(classe__etablissement=etab, date=today, statut='absent').count()
            eleves_payes = Paiement.objects.filter(
                etablissement=etab, statut='valide',
                date_paiement__month=today.month, date_paiement__year=today.year
            ).values_list('eleve_id', flat=True)
            stats['eleves_retard'] = get_eleves_actifs(etab).exclude(pk__in=eleves_payes).count()
            for i in range(6, -1, -1):
                d = today - datetime.timedelta(days=i)
                total = float(Paiement.objects.filter(etablissement=etab, date_paiement__date=d, statut='valide').aggregate(t=Sum('montant'))['t'] or 0)
                chart_paiements.append({'jour': d.strftime('%a %d/%m'), 'total': total})
            cache.set(cache_key, {'stats': stats, 'chart': chart_paiements}, 300)
        else:
            stats = cached['stats']
            chart_paiements = cached['chart']

        paiements_recent = Paiement.objects.filter(etablissement=etab, statut='valide').select_related('eleve','type_frais').order_by('-date_paiement')[:6]
        classes_data = get_classes_actives(etab, annee).select_related('niveau').annotate(nb=Count('inscriptions', filter=Q(inscriptions__is_active=True))) if annee else []

        # Notifications non lues (pour admin)
        if request.user.is_admin:
            stats['notifs_non_lues'] = LogModificationNote.objects.filter(
                note_periode__eleve__etablissement=etab,
                notif_envoyee=True, notif_lue=False
            ).count()

    elif request.user.role == 'super_admin':
        stats['total_etablissements'] = Etablissement.objects.filter(is_active=True).count()
        stats['total_eleves'] = Eleve.objects.filter(is_active=True).count()
        stats['total_users'] = User.objects.filter(is_active=True).count()
        stats['recettes_mois'] = float(Paiement.objects.filter(statut='valide', date_paiement__month=today.month).aggregate(t=Sum('montant'))['t'] or 0)
        return render(request, 'core/dashboard_super.html', {
            'stats': stats,
            'etablissements': Etablissement.objects.filter(is_active=True).annotate(nb_eleves=Count('eleves', filter=Q(eleves__is_active=True))),
        })

    return render(request, 'core/dashboard.html', {
        'stats': stats, 'paiements_recent': paiements_recent,
        'classes_data': classes_data, 'chart_paiements': json.dumps(chart_paiements), 'today': today,
    })


@login_required
def changer_etablissement(request, etab_id):
    if request.user.role == 'super_admin':
        try:
            etab = Etablissement.objects.get(pk=etab_id, is_active=True)
            request.session['etablissement_id'] = etab.pk
        except Etablissement.DoesNotExist:
            pass
    return redirect('dashboard')


@login_required
def notifications(request):
    """Liste des notifications de modifications de notes."""
    if not request.user.is_admin:
        return redirect('dashboard')
    etab = request.etablissement
    logs = LogModificationNote.objects.filter(
        note_periode__eleve__etablissement=etab, notif_envoyee=True
    ).select_related('modifie_par','note_periode__eleve','note_periode__matiere','note_periode__classe').order_by('-date_modif')[:50]
    LogModificationNote.objects.filter(note_periode__eleve__etablissement=etab, notif_lue=False).update(notif_lue=True)
    return render(request, 'core/notifications.html', {'logs': logs})


@login_required
def marquer_notif_lue(request, pk):
    log = LogModificationNote.objects.filter(pk=pk).first()
    if log: log.notif_lue = True; log.save()
    return redirect('notifications')
