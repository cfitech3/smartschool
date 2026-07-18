from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Sum, Q
from django.utils import timezone
from .models import Etablissement, AnneeScolaire, JournalAction, ParametresReseau
from accounts.models import User
from eleves.models import Eleve
from finances.models import Paiement
import datetime


def superadmin_required(fn):
    def w(request, *a, **k):
        if not request.user.is_authenticated or request.user.role != 'super_admin':
            messages.error(request, "Accès réservé au Super Administrateur.")
            return redirect('dashboard')
        return fn(request, *a, **k)
    w.__name__ = fn.__name__
    return w


# ── CHANTIER 2 : Dashboard super admin enrichi ───────────────────────────────

@login_required
@superadmin_required
def liste_etablissements(request):
    today = timezone.now().date()
    etablissements = Etablissement.objects.all().order_by('nom').annotate(
        nb_eleves=Count('eleves', filter=Q(eleves__is_active=True)),
        nb_users=Count('utilisateurs', filter=Q(utilisateurs__is_active=True)),
    )

    # Stats globales
    stats = {
        'total_etablissements': etablissements.count(),
        'actifs': etablissements.filter(is_active=True).count(),
        'inactifs': etablissements.filter(is_active=False).count(),
        'total_eleves': Eleve.objects.filter(is_active=True).count(),
        'total_users': User.objects.filter(is_active=True).exclude(role='super_admin').count(),
        'recettes_mois': float(Paiement.objects.filter(
            statut='valide',
            date_paiement__month=today.month,
            date_paiement__year=today.year,
        ).aggregate(t=Sum('montant'))['t'] or 0),
    }

    # Recettes par établissement ce mois
    for e in etablissements:
        e.recettes_mois = float(Paiement.objects.filter(
            etablissement=e, statut='valide',
            date_paiement__month=today.month,
            date_paiement__year=today.year,
        ).aggregate(t=Sum('montant'))['t'] or 0)
        e.nb_paiements_jour = Paiement.objects.filter(
            etablissement=e, statut='valide',
            date_paiement__date=today,
        ).count()

    derniers_users = User.objects.exclude(role='super_admin').select_related('etablissement').order_by('-date_creation')[:8]

    return render(request, 'etablissements/superadmin/liste.html', {
        'etablissements': etablissements,
        'stats': stats,
        'derniers_users': derniers_users,
        'today': today,
    })


# ── CHANTIER 1 : Vue données d'un établissement (isolation vérifiée) ─────────

@login_required
@superadmin_required
def voir_etablissement(request, pk):
    """Super admin voit les données complètes d'un établissement sans y basculer."""
    etab = get_object_or_404(Etablissement, pk=pk)
    today = timezone.now().date()
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()

    eleves = Eleve.objects.filter(etablissement=etab, is_active=True)
    users = User.objects.filter(etablissement=etab, is_active=True).exclude(role__in=['parent', 'eleve'])
    paiements_recents = Paiement.objects.filter(
        etablissement=etab, statut='valide'
    ).select_related('eleve', 'type_frais').order_by('-date_paiement')[:10]

    recettes_mois = float(Paiement.objects.filter(
        etablissement=etab, statut='valide',
        date_paiement__month=today.month,
        date_paiement__year=today.year,
    ).aggregate(t=Sum('montant'))['t'] or 0)

    # Chart 7 derniers jours
    chart = []
    for i in range(6, -1, -1):
        d = today - datetime.timedelta(days=i)
        total = float(Paiement.objects.filter(
            etablissement=etab, date_paiement__date=d, statut='valide'
        ).aggregate(t=Sum('montant'))['t'] or 0)
        chart.append({'jour': d.strftime('%d/%m'), 'total': total})

    import json
    return render(request, 'etablissements/superadmin/voir_etab.html', {
        'etab': etab,
        'annee': annee,
        'nb_eleves': eleves.count(),
        'nb_users': users.count(),
        'users': users.order_by('role', 'last_name'),
        'paiements_recents': paiements_recents,
        'recettes_mois': recettes_mois,
        'chart': json.dumps(chart),
        'today': today,
    })


# ── CHANTIER 4 : Gestion comptes à distance (reset mdp, bloquer) ─────────────

@login_required
@superadmin_required
def gestion_comptes_etab(request, pk):
    """Super admin gère tous les comptes d'un établissement."""
    etab = get_object_or_404(Etablissement, pk=pk)
    users = User.objects.filter(etablissement=etab).exclude(role='super_admin').order_by('role', 'last_name')

    if request.method == 'POST':
        action = request.POST.get('action')
        u_pk = request.POST.get('user_pk')

        if not u_pk:
            messages.error(request, "Utilisateur non spécifié.")
            return redirect('gestion_comptes_etab', pk=pk)

        # Vérifier que l'utilisateur appartient bien à cet établissement
        user_cible = get_object_or_404(User, pk=u_pk, etablissement=etab)

        if action == 'reset_mdp':
            nouveau_mdp = request.POST.get('nouveau_mdp', '').strip()
            if len(nouveau_mdp) < 6:
                messages.error(request, "Le mot de passe doit faire au moins 6 caractères.")
            else:
                user_cible.set_password(nouveau_mdp)
                user_cible.save()
                JournalAction.log(request, 'reset_mdp', cible=user_cible.username,
                                  etablissement=etab, detail='Reset mdp super admin')
                messages.success(request, f"✅ Mot de passe réinitialisé pour {user_cible.get_full_name() or user_cible.username}.")

        elif action == 'bloquer':
            user_cible.is_active = False
            user_cible.save()
            JournalAction.log(request, 'bloquer_compte', cible=user_cible.username, etablissement=etab)
            messages.warning(request, f"🔒 Compte de {user_cible.get_full_name() or user_cible.username} bloqué.")

        elif action == 'debloquer':
            user_cible.is_active = True
            user_cible.save()
            JournalAction.log(request, 'debloquer_compte', cible=user_cible.username, etablissement=etab)
            messages.success(request, f"✅ Compte de {user_cible.get_full_name() or user_cible.username} réactivé.")

        elif action == 'supprimer':
            nom = user_cible.get_full_name() or user_cible.username
            user_cible.delete()
            messages.success(request, f"🗑️ Compte de {nom} supprimé.")

        return redirect('gestion_comptes_etab', pk=pk)

    return render(request, 'etablissements/superadmin/gestion_comptes.html', {
        'etab': etab,
        'users': users,
        'roles': User.ROLES,
    })


# ── Toggle rapide actif/inactif établissement ─────────────────────────────────

@login_required
@superadmin_required
def toggle_etablissement(request, pk):
    """Active ou désactive un établissement en un clic."""
    etab = get_object_or_404(Etablissement, pk=pk)
    etab.is_active = not etab.is_active
    etab.save()
    statut = "réactivé ✅" if etab.is_active else "suspendu 🔒"
    type_log = 'reactiver_etab' if etab.is_active else 'suspendre_etab'
    JournalAction.log(request, type_log, cible=etab.nom, etablissement=etab,
                      detail=f"Établissement {statut}")
    messages.success(request, f"Établissement '{etab.nom}' {statut}.")
    return redirect('liste_etablissements')


# ── Créer / modifier établissement ───────────────────────────────────────────

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
            JournalAction.log(request, 'creer_etab', cible=nom, etablissement=etab,
                              detail=f'Code portail: {code}')
            messages.success(request, f"Établissement '{nom}' créé ! Portail : /auth/portail/{code}/")
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
        etab.is_active = 'is_active' in request.POST
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
