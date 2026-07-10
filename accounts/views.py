from django.shortcuts import render
from django.shortcuts import render, redirect
from accounts.permissions import role_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import User

def login_view(request):
    if request.user.is_authenticated: return redirect('dashboard')
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user: login(request, user); return redirect(request.GET.get('next','dashboard'))
        else: messages.error(request, 'Identifiant ou mot de passe incorrect.')
    return render(request, 'accounts/login.html', {})

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
