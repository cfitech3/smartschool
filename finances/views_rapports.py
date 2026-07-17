"""
Rapports avancés pour le directeur et le comptable.
"""
import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q, Avg
from django.utils import timezone
from accounts.permissions import permission_required
from .models import Paiement, TypeFrais
from eleves.models import Eleve, Inscription
from core.cycle_filter import get_eleves_actifs, get_classes_actives
from etablissements.models import AnneeScolaire


@login_required
@permission_required('finances')
def rapport_retards(request):
    """Liste des élèves en retard de paiement avec contact tuteur."""
    etab = request.etablissement
    today = timezone.now().date()
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()

    mois = int(request.GET.get('mois', today.month))
    annee_val = int(request.GET.get('annee', today.year))

    payes_ids = Paiement.objects.filter(
        etablissement=etab, statut='valide',
        date_paiement__month=mois, date_paiement__year=annee_val
    ).values_list('eleve_id', flat=True).distinct()

    eleves_retard = get_eleves_actifs(etab).exclude(
        pk__in=payes_ids
    ).select_related('tuteur').prefetch_related('inscriptions__classe').order_by('nom', 'prenom')

    # Montant total dû estimé
    types_frais = TypeFrais.objects.filter(etablissement=etab)
    montant_moyen = float(types_frais.aggregate(t=Sum('montant_defaut'))['t'] or 0) if types_frais.exists() else 0

    MOIS_FR = ['', 'Janvier','Février','Mars','Avril','Mai','Juin',
               'Juillet','Août','Septembre','Octobre','Novembre','Décembre']

    return render(request, 'finances/rapport_retards.html', {
        'eleves_retard': eleves_retard,
        'mois': mois, 'annee_val': annee_val,
        'nb_retard': eleves_retard.count(),
        'mois_fr': MOIS_FR[mois],
        'today': today, 'annee': annee,
        'mois_choices': [(i, MOIS_FR[i]) for i in range(1, 13)],
        'annees': range(today.year - 1, today.year + 1),
    })


@login_required
@permission_required('finances')
def rapport_bilan_annuel(request):
    """Bilan de fin d'année scolaire."""
    etab = request.etablissement
    today = timezone.now().date()
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()

    annee_val = int(request.GET.get('annee', today.year))
    MOIS_FR = ['', 'Janv','Févr','Mars','Avr','Mai','Juin',
               'Juil','Août','Sept','Oct','Nov','Déc']

    # Recettes par mois
    recettes_mois = []
    total_annee = 0
    for m in range(1, 13):
        t = float(Paiement.objects.filter(
            etablissement=etab, statut='valide',
            date_paiement__month=m, date_paiement__year=annee_val
        ).aggregate(t=Sum('montant'))['t'] or 0)
        recettes_mois.append({'mois': MOIS_FR[m], 'total': t})
        total_annee += t

    # Recettes par type de frais
    par_type = Paiement.objects.filter(
        etablissement=etab, statut='valide',
        date_paiement__year=annee_val
    ).values('type_frais__nom').annotate(
        total=Sum('montant'), nb=Count('id')
    ).order_by('-total')

    # Stats élèves
    nb_eleves = get_eleves_actifs(etab).count()
    nb_classes = get_classes_actives(etab, annee).count() if annee else 0
    eleves_jamais_payes = get_eleves_actifs(etab).exclude(
        pk__in=Paiement.objects.filter(
            etablissement=etab, statut='valide',
            date_paiement__year=annee_val
        ).values_list('eleve_id', flat=True)
    ).count()

    import json
    chart_data = json.dumps([{'mois': r['mois'], 'total': r['total']} for r in recettes_mois])

    return render(request, 'finances/rapport_bilan_annuel.html', {
        'recettes_mois': recettes_mois,
        'par_type': par_type,
        'total_annee': total_annee,
        'nb_eleves': nb_eleves,
        'nb_classes': nb_classes,
        'eleves_jamais_payes': eleves_jamais_payes,
        'taux_paiement': round((nb_eleves - eleves_jamais_payes) / nb_eleves * 100, 1) if nb_eleves else 0,
        'annee_val': annee_val,
        'chart_data': chart_data,
        'today': today, 'annee': annee,
        'annees': range(today.year - 2, today.year + 1),
    })
