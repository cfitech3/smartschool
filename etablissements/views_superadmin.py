from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Etablissement, AnneeScolaire


def superadmin_required(fn):
    def w(request, *a, **k):
        if not request.user.is_authenticated or request.user.role != 'super_admin':
            messages.error(request, "Accès réservé au Super Administrateur.")
            return redirect('dashboard')
        return fn(request, *a, **k)
    w.__name__ = fn.__name__
    return w


@login_required
@superadmin_required
def liste_etablissements(request):
    etablissements = Etablissement.objects.all().order_by('nom')
    return render(request, 'etablissements/superadmin/liste.html', {
        'etablissements': etablissements,
    })


@login_required
@superadmin_required
def creer_etablissement(request):
    if request.method == 'POST':
        nom = request.POST.get('nom', '').strip()
        code = request.POST.get('code', '').strip().upper()
        type_etab = request.POST.get('type', 'ecole')
        adresse = request.POST.get('adresse', '')
        telephone = request.POST.get('telephone', '')
        email = request.POST.get('email', '')
        directeur = request.POST.get('directeur', '')
        slogan = request.POST.get('slogan', '')
        couleur_principale = request.POST.get('couleur_principale', '#1565C0')
        couleur_secondaire = request.POST.get('couleur_secondaire', '#0D47A1')

        if not nom or not code:
            messages.error(request, "Le nom et le code sont obligatoires.")
        elif Etablissement.objects.filter(code=code).exists():
            messages.error(request, f"Un établissement avec le code '{code}' existe déjà.")
        else:
            etab = Etablissement.objects.create(
                nom=nom, code=code, type=type_etab, adresse=adresse,
                telephone=telephone, email=email, directeur=directeur,
                slogan=slogan, couleur_principale=couleur_principale,
                couleur_secondaire=couleur_secondaire,
            )
            if request.FILES.get('logo'):
                etab.logo = request.FILES['logo']
                etab.save()
            messages.success(request, f"Établissement '{nom}' créé avec succès !")
            return redirect('liste_etablissements')

    return render(request, 'etablissements/superadmin/form.html', {
        'mode': 'creer',
        'types': Etablissement.TYPES,
    })


@login_required
@superadmin_required
def modifier_etablissement(request, pk):
    etab = get_object_or_404(Etablissement, pk=pk)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'supprimer':
            nom = etab.nom
            etab.delete()
            messages.success(request, f"Établissement '{nom}' supprimé.")
            return redirect('liste_etablissements')

        etab.nom = request.POST.get('nom', etab.nom).strip()
        etab.code = request.POST.get('code', etab.code).strip().upper()
        etab.type = request.POST.get('type', etab.type)
        etab.adresse = request.POST.get('adresse', etab.adresse)
        etab.telephone = request.POST.get('telephone', etab.telephone)
        etab.email = request.POST.get('email', etab.email)
        etab.directeur = request.POST.get('directeur', etab.directeur)
        etab.slogan = request.POST.get('slogan', etab.slogan)
        etab.couleur_principale = request.POST.get('couleur_principale', etab.couleur_principale)
        etab.couleur_secondaire = request.POST.get('couleur_secondaire', etab.couleur_secondaire)
        etab.is_active = bool(request.POST.get('is_active'))
        if request.FILES.get('logo'):
            etab.logo = request.FILES['logo']
        etab.save()
        messages.success(request, f"'{etab.nom}' mis à jour.")
        return redirect('liste_etablissements')

    return render(request, 'etablissements/superadmin/form.html', {
        'mode': 'modifier',
        'etab': etab,
        'types': Etablissement.TYPES,
    })
