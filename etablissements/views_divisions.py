from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Division, CycleActif, Cycle
from accounts.models import User

def req_admin(fn):
    def w(request, *a, **k):
        if not request.user.is_admin or not request.etablissement:
            return redirect("dashboard")
        return fn(request, *a, **k)
    w.__name__ = fn.__name__; return w


@login_required
@req_admin
def liste_divisions(request):
    etab     = request.etablissement
    divisions = Division.objects.filter(etablissement=etab).prefetch_related('cycles')
    cycles_actifs = CycleActif.objects.filter(etablissement=etab).select_related('cycle')
    tous_cycles   = Cycle.objects.filter(etablissement=etab)
    # Cycles non encore actifs
    cycles_actifs_ids = cycles_actifs.values_list('cycle_id', flat=True)
    cycles_disponibles = tous_cycles.exclude(pk__in=cycles_actifs_ids)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'activer_cycle':
            c_pk = request.POST.get('cycle_pk')
            c = get_object_or_404(Cycle, pk=c_pk, etablissement=etab)
            _, created = CycleActif.objects.get_or_create(
                etablissement=etab, cycle=c,
                defaults={'ordre': cycles_actifs.count() + 1}
            )
            if created:
                messages.success(request, f"Cycle '{c.nom}' activé.")
            else:
                messages.info(request, f"Ce cycle est déjà actif.")

        elif action == 'desactiver_cycle':
            c_pk = request.POST.get('cycle_pk')
            CycleActif.objects.filter(etablissement=etab, cycle_id=c_pk).delete()
            messages.success(request, "Cycle désactivé.")

        return redirect('liste_divisions')

    return render(request, 'etablissements/divisions/liste.html', {
        'divisions': divisions,
        'cycles_actifs': cycles_actifs,
        'cycles_disponibles': cycles_disponibles,
    })


@login_required
@req_admin
def creer_division(request):
    etab = request.etablissement
    cycles_actifs = CycleActif.objects.filter(etablissement=etab).select_related('cycle')
    admins = User.objects.filter(etablissement=etab, role__in=['admin', 'comptable', 'surveillant'])

    if request.method == 'POST':
        nom  = request.POST.get('nom', '').strip()
        code = request.POST.get('code', '').strip().upper()
        if not nom:
            messages.error(request, "Le nom est obligatoire.")
        elif Division.objects.filter(etablissement=etab, nom=nom).exists():
            messages.error(request, f"Une division '{nom}' existe déjà.")
        else:
            div = Division.objects.create(
                etablissement=etab,
                nom=nom,
                code=code,
                directeur_nom=request.POST.get('directeur_nom', ''),
                entete_ligne1=request.POST.get('entete_ligne1', etab.nom),
                entete_ligne2=request.POST.get('entete_ligne2', ''),
                couleur_principale=request.POST.get('couleur_principale', '#1565C0'),
                telephone=request.POST.get('telephone', ''),
                adresse=request.POST.get('adresse', ''),
                ordre=Division.objects.filter(etablissement=etab).count() + 1,
            )
            # Rattacher les cycles sélectionnés
            cycles_ids = request.POST.getlist('cycles')
            if cycles_ids:
                div.cycles.set(Cycle.objects.filter(pk__in=cycles_ids, etablissement=etab))
            # Rattacher le directeur si choisi
            dir_pk = request.POST.get('directeur_user')
            if dir_pk:
                try:
                    dir_user = User.objects.get(pk=dir_pk, etablissement=etab)
                    div.directeur_user = dir_user
                    div.save()
                    dir_user.division = div
                    dir_user.save()
                except User.DoesNotExist:
                    pass
            messages.success(request, f"Division '{nom}' créée.")
            return redirect('liste_divisions')

    return render(request, 'etablissements/divisions/form.html', {
        'mode': 'creer',
        'cycles_actifs': cycles_actifs,
        'admins': admins,
        'etab': etab,
    })


@login_required
@req_admin
def modifier_division(request, pk):
    etab = request.etablissement
    div  = get_object_or_404(Division, pk=pk, etablissement=etab)
    cycles_actifs = CycleActif.objects.filter(etablissement=etab).select_related('cycle')
    admins = User.objects.filter(etablissement=etab, role__in=['admin', 'comptable', 'surveillant'])

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'supprimer':
            div.delete()
            messages.success(request, "Division supprimée.")
            return redirect('liste_divisions')

        div.nom  = request.POST.get('nom', div.nom).strip()
        div.code = request.POST.get('code', div.code).strip().upper()
        div.directeur_nom       = request.POST.get('directeur_nom', '')
        div.entete_ligne1       = request.POST.get('entete_ligne1', '')
        div.entete_ligne2       = request.POST.get('entete_ligne2', '')
        div.couleur_principale  = request.POST.get('couleur_principale', '#1565C0')
        div.telephone           = request.POST.get('telephone', '')
        div.adresse             = request.POST.get('adresse', '')
        div.save()

        cycles_ids = request.POST.getlist('cycles')
        div.cycles.set(Cycle.objects.filter(pk__in=cycles_ids, etablissement=etab))

        dir_pk = request.POST.get('directeur_user')
        if dir_pk:
            try:
                dir_user = User.objects.get(pk=dir_pk, etablissement=etab)
                div.directeur_user = dir_user
                div.save()
                # Mettre à jour le lien sur l'user
                User.objects.filter(etablissement=etab, division=div).update(division=None)
                dir_user.division = div
                dir_user.save()
            except User.DoesNotExist:
                pass
        else:
            div.directeur_user = None
            div.save()

        messages.success(request, f"Division '{div.nom}' mise à jour.")
        return redirect('liste_divisions')

    return render(request, 'etablissements/divisions/form.html', {
        'mode': 'modifier',
        'div': div,
        'cycles_actifs': cycles_actifs,
        'admins': admins,
        'etab': etab,
        'div_cycles_ids': list(div.cycles.values_list('pk', flat=True)),
    })
