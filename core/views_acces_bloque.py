from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required


@login_required
def acces_bloque(request):
    """Page affichée quand l'établissement est désactivé par le super admin."""
    etab = None
    if hasattr(request.user, 'etablissement'):
        etab = request.user.etablissement
    return render(request, 'core/acces_bloque.html', {'etab': etab})
