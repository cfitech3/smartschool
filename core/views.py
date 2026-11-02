from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from accounts.permissions import role_required
from django.db.models import Count, Sum, Q
from django.utils import timezone
from django.core.cache import cache
from eleves.models import Eleve, Presence
from finances.models import Paiement
from etablissements.models import Etablissement, Classe, AnneeScolaire
from accounts.models import User
from notes.models import LogModificationNote
import json, datetime
from core.cycle_filter import get_cycles_actifs_ids, get_classes_actives, get_eleves_actifs, get_inscriptions_actives


@login_required
def dashboard(request):
    """Délègue au routeur de tableau de bord principal par rôle (views_dashboard.dashboard)."""
    from core.views_dashboard import dashboard as role_dashboard
    return role_dashboard(request)


@login_required
def changer_etablissement(request, etab_id):
    """Super admin bascule sur un établissement (actif ou suspendu)."""
    from accounts.models import User as UserModel
    # En mode espionnage, l'utilisateur réel est stocké en session
    original_pk = request.session.get('_impersonate_original_pk')
    is_super = request.user.role == 'super_admin'
    if not is_super and original_pk:
        try:
            original = UserModel.objects.get(pk=original_pk)
            is_super = original.role == 'super_admin'
        except UserModel.DoesNotExist:
            pass
    if is_super:
        try:
            etab = Etablissement.objects.get(pk=etab_id)  # Sans filtre is_active
            request.session['etablissement_id'] = etab.pk
        except Etablissement.DoesNotExist:
            pass
    return redirect('dashboard')


@login_required
@role_required('admin')
def notifications(request):
    """Liste des notifications de modifications de notes (réservée à la direction)."""
    etab = request.etablissement
    logs = list(
        LogModificationNote.objects.filter(
            note_periode__eleve__etablissement=etab, notif_envoyee=True
        ).select_related('modifie_par','note_periode__eleve','note_periode__matiere','note_periode__classe').order_by('-date_modif')[:50]
    )
    LogModificationNote.objects.filter(note_periode__eleve__etablissement=etab, notif_lue=False).update(notif_lue=True)
    return render(request, 'core/notifications.html', {'logs': logs})


@login_required
@role_required('admin')
def marquer_notif_lue(request, pk):
    etab = request.etablissement
    log = LogModificationNote.objects.filter(pk=pk, note_periode__eleve__etablissement=etab).first()
    if log: log.notif_lue = True; log.save()
    return redirect('notifications')
