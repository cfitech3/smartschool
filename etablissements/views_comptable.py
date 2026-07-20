"""
Vue enseignants pour le comptable :
- Liste des enseignants avec leurs salaires
- Détail avec affectations (lecture seule)
- Modification du salaire uniquement
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Enseignant, AffectationMatiere, AnneeScolaire
from accounts.permissions import role_required


@login_required
@role_required('comptable', 'admin', 'super_admin')
def enseignants_comptable(request):
    """Liste des enseignants avec salaires — vue comptable."""
    etab = request.etablissement
    enseignants = Enseignant.objects.filter(
        etablissement=etab
    ).select_related('user').order_by('user__last_name', 'user__first_name')

    q = request.GET.get('q', '')
    if q:
        from django.db.models import Q
        enseignants = enseignants.filter(
            Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q)
        )

    from django.db.models import Sum
    total_masse_salariale = enseignants.filter(
        salaire__isnull=False
    ).aggregate(t=Sum('salaire'))['t'] or 0

    return render(request, 'etablissements/comptable/liste_enseignants.html', {
        'enseignants': enseignants,
        'q': q,
        'total': enseignants.count(),
        'masse_salariale': total_masse_salariale,
    })


@login_required
@role_required('comptable', 'admin', 'super_admin')
def detail_enseignant_comptable(request, pk):
    """Détail enseignant avec affectations — lecture seule + modifier salaire."""
    etab = request.etablissement
    ens = get_object_or_404(Enseignant, pk=pk, etablissement=etab)
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
    affs = AffectationMatiere.objects.filter(
        enseignant=ens, annee=annee
    ).select_related('matiere', 'classe__niveau') if annee else []

    if request.method == 'POST':
        salaire_str = request.POST.get('salaire', '').strip()
        try:
            if salaire_str:
                ens.salaire = int(salaire_str.replace(' ', '').replace(',', ''))
            else:
                ens.salaire = None
            ens.save()
            messages.success(
                request,
                f"✅ Salaire de {ens.nom_complet} mis à jour : "
                f"{int(ens.salaire):,} FCFA/mois" if ens.salaire else "✅ Salaire supprimé."
            )
        except ValueError:
            messages.error(request, "Montant invalide.")
        return redirect('detail_enseignant_comptable', pk=pk)

    return render(request, 'etablissements/comptable/detail_enseignant.html', {
        'enseignant': ens,
        'affectations': affs,
        'annee': annee,
    })
