from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count
from accounts.models import JournalConnexion
from etablissements.models import Etablissement
import datetime


@login_required
def journal_connexions(request):
    if request.user.role != 'super_admin':
        return redirect('dashboard')
    today = timezone.now().date()
    etab_id = request.GET.get('etab', '')
    statut  = request.GET.get('statut', '')
    date_f  = request.GET.get('date', '')
    q       = request.GET.get('q', '')

    qs = JournalConnexion.objects.select_related('user', 'etablissement').order_by('-date')
    if etab_id: qs = qs.filter(etablissement_id=etab_id)
    if statut:  qs = qs.filter(statut=statut)
    if date_f:
        try:
            d = datetime.date.fromisoformat(date_f); qs = qs.filter(date__date=d)
        except ValueError: pass
    if q: qs = qs.filter(username__icontains=q)

    stats = {
        'total_aujourd_hui':  JournalConnexion.objects.filter(date__date=today).count(),
        'succes_aujourd_hui': JournalConnexion.objects.filter(date__date=today, statut='succes').count(),
        'echecs_aujourd_hui': JournalConnexion.objects.filter(date__date=today, statut__in=['echec','bloque']).count(),
        'total_7j':           JournalConnexion.objects.filter(date__gte=timezone.now()-datetime.timedelta(days=7)).count(),
    }
    ips_suspectes = JournalConnexion.objects.filter(
        statut__in=['echec','bloque'],
        date__gte=timezone.now()-datetime.timedelta(hours=24)
    ).values('ip').annotate(nb=Count('id')).filter(nb__gte=3).order_by('-nb')[:5]

    return render(request, 'accounts/journal_connexions.html', {
        'logs': qs[:200], 'stats': stats,
        'etabs': Etablissement.objects.all().order_by('nom'),
        'statuts': JournalConnexion.STATUTS,
        'etab_id': etab_id, 'statut': statut, 'date_filtre': date_f,
        'username_q': q, 'nb_total': qs.count(),
        'ips_suspectes': ips_suspectes, 'today': today,
    })
