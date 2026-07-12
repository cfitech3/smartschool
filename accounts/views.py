from django.shortcuts import render, redirect
from accounts.permissions import role_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import User

def login_view(request):
    if request.user.is_authenticated: return redirect('dashboard')
    if request.method == 'POST':
        # P3.5 : Rate limiting sur le login
        from django.core.cache import cache
        
        # Récupération de l'IP du client (gère les proxies basiques)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
            
        cache_key = f'login_attempts_{ip}'
        attempts = cache.get(cache_key, 0)
        
        if attempts >= 5:
            messages.error(request, 'Trop de tentatives infructueuses. Veuillez réessayer dans 15 minutes.')
            return render(request, 'accounts/login.html', {})
            
        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user:
            cache.delete(cache_key) # Réinitialiser après succès
            login(request, user)
            return redirect(request.GET.get('next','dashboard'))
        else:
            cache.set(cache_key, attempts + 1, 900) # Bloquer pendant 15 mins (900 sec)
            messages.error(request, f'Identifiant ou mot de passe incorrect. ({4 - attempts} essais restants)')
    return render(request, 'accounts/login.html', {})

def login_portail(request, code_etab):
    if request.user.is_authenticated: return redirect('dashboard')
    from etablissements.models import Etablissement
    from django.shortcuts import get_object_or_404
    etab = get_object_or_404(Etablissement, code__iexact=code_etab, is_active=True)
    
    if request.method == 'POST':
        # Same rate limiting logic
        from django.core.cache import cache
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        ip = x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')
        cache_key = f'login_attempts_{ip}'
        attempts = cache.get(cache_key, 0)
        
        if attempts >= 5:
            messages.error(request, 'Trop de tentatives infructueuses. Veuillez réessayer dans 15 minutes.')
            return render(request, 'accounts/login.html', {'portail_etab': etab})
            
        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user:
            cache.delete(cache_key)
            login(request, user)
            return redirect(request.GET.get('next','dashboard'))
        else:
            cache.set(cache_key, attempts + 1, 900)
            messages.error(request, f'Identifiant ou mot de passe incorrect. ({4 - attempts} essais restants)')
            
    return render(request, 'accounts/login.html', {'portail_etab': etab})

def logout_view(request):
    logout(request); return redirect('login')

@login_required
def profil(request):
    return render(request, 'accounts/profil.html', {'user': request.user})

@login_required
@role_required('admin')
def liste_utilisateurs(request):
    if not request.user.is_admin: return redirect('dashboard')
    etab = request.etablissement
    users = User.objects.filter(etablissement=etab).order_by('role','last_name') if etab else []
    return render(request, 'accounts/liste_utilisateurs.html', {'users': users})
