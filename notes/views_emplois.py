from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import JsonResponse
from .models import EmploiDuTemps, Matiere
from etablissements.models import Classe, AnneeScolaire, Enseignant
from accounts.permissions import require_etab as req
from core.cycle_filter import get_classes_actives

HEURES = [
    "07:00", "07:30", "08:00", "08:30", "09:00", "09:30", "10:00", "10:30",
    "11:00", "11:30", "12:00", "12:30", "13:00", "13:30", "14:00", "14:30",
    "15:00", "15:30", "16:00", "16:30", "17:00", "17:30", "18:00"
]
JOURS_ORDRE = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"]


def detecter_conflits_creneau(etab, annee, classe, jour, hd, hf, ens_user=None, salle='', exclude_pk=None):
    """
    Détecte tous les conflits horaires (Horaire, Classe, Enseignant, Salle)
    et retourne une liste de messages explicites.
    """
    conflits = []
    if not (jour and hd and hf):
        return conflits
    if hd >= hf:
        conflits.append("L'heure de fin doit être strictement postérieure à l'heure de début.")
        return conflits

    base_qs = EmploiDuTemps.objects.filter(
        etablissement=etab, jour=jour,
        heure_debut__lt=hf, heure_fin__gt=hd
    ).select_related('classe', 'matiere', 'enseignant')
    if annee:
        base_qs = base_qs.filter(classe__annee=annee)
    if exclude_pk:
        base_qs = base_qs.exclude(pk=exclude_pk)

    if classe:
        c_cl = base_qs.filter(classe=classe).first()
        if c_cl:
            conflits.append(
                f"Conflit Classe : {classe.nom} a déjà « {c_cl.matiere.nom} » de {c_cl.heure_debut} à {c_cl.heure_fin}."
            )

    if ens_user:
        c_ens = base_qs.filter(enseignant=ens_user).first()
        if c_ens:
            nom_ens = ens_user.get_full_name() or ens_user.username
            salle_info = f" (Salle {c_ens.salle})" if c_ens.salle else ""
            conflits.append(
                f"Conflit Enseignant : {nom_ens} enseigne déjà « {c_ens.matiere.nom} » en {c_ens.classe.nom} de {c_ens.heure_debut} à {c_ens.heure_fin}{salle_info}."
            )

    salle_clean = (salle or '').strip()
    if salle_clean:
        c_salle = base_qs.filter(salle__iexact=salle_clean).first()
        if c_salle:
            conflits.append(
                f"Conflit de Salle : La salle « {salle_clean} » est déjà occupée par {c_salle.classe.nom} ({c_salle.matiere.nom}) de {c_salle.heure_debut} à {c_salle.heure_fin}."
            )

    return conflits


@login_required
@req
def verifier_conflit_emploi(request):
    """API AJAX de vérification en temps réel des conflits d'emploi du temps."""
    etab = request.etablissement
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
    classe_id = request.GET.get('classe')
    jour = request.GET.get('jour', '')
    hd = request.GET.get('heure_debut', '')
    hf = request.GET.get('heure_fin', '')
    ens_id = request.GET.get('enseignant', '')
    salle = request.GET.get('salle', '')

    classe = Classe.objects.filter(pk=classe_id, etablissement=etab).first() if classe_id else None
    ens_user = None
    if ens_id and str(ens_id).isdigit():
        ens_obj = Enseignant.objects.filter(pk=int(ens_id), etablissement=etab).select_related('user').first()
        if ens_obj:
            ens_user = ens_obj.user

    conflits = detecter_conflits_creneau(
        etab, annee, classe, jour, hd, hf, ens_user=ens_user, salle=salle
    )
    return JsonResponse({'ok': len(conflits) == 0, 'conflits': conflits})


@login_required
@req
def emploi_du_temps(request):
    etab = request.etablissement
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
    classes = get_classes_actives(etab, annee, user=request.user) if annee else Classe.objects.none()
    matieres = Matiere.objects.filter(etablissement=etab)
    enseignants = Enseignant.objects.filter(etablissement=etab).select_related("user")
    classe_id = request.GET.get("classe")
    classe = get_object_or_404(classes, pk=classe_id, etablissement=etab) if classe_id else None
    creneaux = []
    if classe:
        creneaux = list(
            EmploiDuTemps.objects.filter(etablissement=etab, classe=classe)
            .select_related("matiere", "enseignant")
            .order_by("jour", "heure_debut")
        )
    if request.method == "POST" and classe:
        if request.user.role not in ("admin", "super_admin", "secretariat"):
            messages.error(request, "Seule l'administration peut modifier l'emploi du temps.")
            return redirect(f"/notes/emplois/?classe={classe_id}")
        jour = request.POST.get("jour")
        mat_id = request.POST.get("matiere")
        ens_id = request.POST.get("enseignant") or None
        hd = request.POST.get("heure_debut")
        hf = request.POST.get("heure_fin")
        salle = request.POST.get("salle", "").strip()
        if jour and mat_id and hd and hf:
            matiere_obj = get_object_or_404(Matiere, pk=mat_id, etablissement=etab)
            ens_user = None
            if ens_id and str(ens_id).isdigit():
                try:
                    ens_user = Enseignant.objects.get(pk=int(ens_id), etablissement=etab).user
                except Enseignant.DoesNotExist:
                    pass

            conflits = detecter_conflits_creneau(
                etab, annee, classe, jour, hd, hf, ens_user=ens_user, salle=salle
            )
            if conflits:
                for msg in conflits:
                    messages.error(request, msg)
            else:
                EmploiDuTemps.objects.create(
                    etablissement=etab, classe=classe, matiere=matiere_obj,
                    enseignant=ens_user, jour=jour, heure_debut=hd, heure_fin=hf, salle=salle
                )
                messages.success(request, "Créneau ajouté avec succès.")
        return redirect(f"/notes/emplois/?classe={classe_id}")
    return render(request, "notes/emploi_du_temps.html", {
        "classes": classes, "classe": classe, "matieres": matieres,
        "enseignants": enseignants, "creneaux": creneaux,
        "jours": EmploiDuTemps.JOURS, "jours_ordre": JOURS_ORDRE,
        "heures": HEURES, "classe_id": classe_id
    })


@login_required
@require_POST
@req
def supprimer_creneau(request, pk):
    if request.user.role not in ("admin", "super_admin", "secretariat"):
        messages.error(request, "Seule l'administration peut supprimer un créneau.")
        return redirect("emploi_du_temps")
    etab = request.etablissement
    c = get_object_or_404(EmploiDuTemps, pk=pk, etablissement=etab)
    cid = c.classe.pk
    c.delete()
    messages.success(request, "Créneau supprimé.")
    return redirect(f"/notes/emplois/?classe={cid}")
