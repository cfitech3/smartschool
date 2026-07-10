from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Cycle, SerieLycee, MatiereCycle, MatiereSerieCoef, UEUniversite, Niveau, Classe
from notes.models import Matiere

def req_admin(fn):
    def w(request, *a, **k):
        if not request.user.is_admin or not request.etablissement:
            return redirect("dashboard")
        return fn(request, *a, **k)
    w.__name__ = fn.__name__; return w


@login_required
@req_admin
def liste_cycles(request):
    etab   = request.etablissement
    cycles = Cycle.objects.filter(etablissement=etab).prefetch_related(
        'niveaux', 'matieres_defaut__matiere', 'series'
    )
    return render(request, 'etablissements/cycles/liste.html', {
        'cycles': cycles,
        'TYPES': dict(Cycle.TYPES),
    })


@login_required
@req_admin
def detail_cycle(request, pk):
    etab  = request.etablissement
    cycle = get_object_or_404(Cycle, pk=pk, etablissement=etab)
    niveaux  = Niveau.objects.filter(etablissement=etab, cycle=cycle).order_by('ordre')
    matieres_cycle = MatiereCycle.objects.filter(cycle=cycle).select_related('matiere').order_by('ordre')
    toutes_matieres = Matiere.objects.filter(etablissement=etab)
    series = SerieLycee.objects.filter(cycle=cycle) if cycle.is_lycee else []
    ues    = UEUniversite.objects.filter(cycle=cycle).order_by('semestre','code') if cycle.is_universite else []

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_cycle':
            cycle.nom = request.POST.get('nom', cycle.nom)
            cycle.mode_calcul = request.POST.get('mode_calcul', cycle.mode_calcul)
            cycle.note_passage = request.POST.get('note_passage', cycle.note_passage)
            cycle.diplome_prepare = request.POST.get('diplome_prepare', cycle.diplome_prepare)
            cycle.save()
            messages.success(request, "Cycle mis à jour.")

        elif action == 'add_matiere':
            mat_pk = request.POST.get('matiere_pk')
            coef   = request.POST.get('coefficient', 1)
            oblig  = 'est_obligatoire' in request.POST
            if mat_pk:
                mat = get_object_or_404(Matiere, pk=mat_pk, etablissement=etab)
                MatiereCycle.objects.update_or_create(
                    cycle=cycle, matiere=mat,
                    defaults={'coefficient': int(coef), 'est_obligatoire': oblig,
                              'ordre': matieres_cycle.count() + 1}
                )
                messages.success(request, f"Matière '{mat.nom}' ajoutée au cycle.")

        elif action == 'remove_matiere':
            mat_pk = request.POST.get('matiere_pk')
            MatiereCycle.objects.filter(cycle=cycle, matiere_id=mat_pk).delete()
            messages.success(request, "Matière retirée du cycle.")

        elif action == 'update_coef':
            mat_pk = request.POST.get('matiere_pk')
            coef   = request.POST.get('coefficient', 1)
            MatiereCycle.objects.filter(cycle=cycle, matiere_id=mat_pk).update(coefficient=int(coef))
            messages.success(request, "Coefficient mis à jour.")

        elif action == 'add_serie':
            code = request.POST.get('code', '').strip().upper()
            nom  = request.POST.get('nom', '').strip()
            if code and nom:
                SerieLycee.objects.get_or_create(cycle=cycle, code=code, defaults={'nom': nom, 'ordre': len(series)+1})
                messages.success(request, f"Série {code} ajoutée.")

        elif action == 'add_ue':
            UEUniversite.objects.create(
                cycle=cycle,
                code=request.POST.get('code','').strip(),
                nom=request.POST.get('nom','').strip(),
                credits=int(request.POST.get('credits', 3)),
                semestre=int(request.POST.get('semestre', 1)),
                coefficient=int(request.POST.get('coefficient', 1)),
                est_obligatoire='est_obligatoire' in request.POST,
            )
            messages.success(request, "UE ajoutée.")

        return redirect('detail_cycle', pk=cycle.pk)

    return render(request, 'etablissements/cycles/detail.html', {
        'cycle': cycle, 'niveaux': niveaux,
        'matieres_cycle': matieres_cycle,
        'toutes_matieres': toutes_matieres,
        'matieres_ids': [mc.matiere_id for mc in matieres_cycle],
        'series': series, 'ues': ues,
        'MODES': dict(Cycle.MODE_CALCUL),
        'semestres_range': range(1, 9),
    })
