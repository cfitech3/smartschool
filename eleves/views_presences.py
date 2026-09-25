
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count
from .models import Presence, Inscription, Eleve, JourNonOuvre
from etablissements.models import Classe, AnneeScolaire
import datetime
from core.cycle_filter import get_cycles_actifs_ids, get_classes_actives, get_eleves_actifs, get_inscriptions_actives
from accounts.permissions import role_required


def req(fn):
    def w(request, *a, **k):
        if not request.etablissement:
            return redirect("dashboard")
        return fn(request, *a, **k)
    w.__name__ = fn.__name__
    return w


# ══════════════════════════════════════════════════════════════
@login_required
@role_required(['admin', 'super_admin', 'secretariat', 'surveillant', 'enseignant'])
@req
def appel_presences(request):
    etab = request.etablissement
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
    classes = get_classes_actives(etab, annee, user=request.user) if annee else []
    classe_id = request.GET.get("classe")
    date_str = request.GET.get("date", timezone.now().date().isoformat())
    try:
        date_appel = datetime.date.fromisoformat(date_str)
    except Exception:
        date_appel = timezone.now().date()

    classe = None
    eleves_data = []
    appel_fait = False
    jour_non_ouvre = False
    motif_non_ouvre = None

    # Vérifier si le jour est non ouvré (dimanche ou déclaré)
    if classe_id:
        classe = get_object_or_404(Classe, pk=classe_id, etablissement=etab)
        jour_non_ouvre, motif_non_ouvre = JourNonOuvre.est_jour_non_ouvre(etab, date_appel, classe)

    if classe_id and not jour_non_ouvre:
        inscriptions = classe.inscriptions.filter(is_active=True).select_related("eleve").order_by("eleve__nom", "eleve__prenom")
        pex = {p.eleve_id: p for p in Presence.objects.filter(classe=classe, date=date_appel)}
        appel_fait = bool(pex)
        for insc in inscriptions:
            p = pex.get(insc.eleve.pk)
            eleves_data.append({
                "eleve": insc.eleve,
                "statut": p.statut if p else "present",
                "motif": p.motif if p else "",
                "presence_id": p.pk if p else None,
            })

    if request.method == "POST" and classe_id and not jour_non_ouvre:
        classe = get_object_or_404(Classe, pk=classe_id, etablissement=etab)
        saved = 0
        for insc in classe.inscriptions.filter(is_active=True).select_related("eleve"):
            st = request.POST.get(f"statut_{insc.eleve.pk}", "present")
            mo = request.POST.get(f"motif_{insc.eleve.pk}", "")
            Presence.objects.update_or_create(
                eleve=insc.eleve, classe=classe, date=date_appel,
                defaults={"statut": st, "motif": mo, "enregistre_par": request.user}
            )
            saved += 1
        messages.success(request, f"Appel enregistré : {saved} élève(s) — {classe.nom} — {date_appel.strftime('%d/%m/%Y')}")
        return redirect(f"{request.path}?classe={classe_id}&date={date_appel}")

    # Jours non ouvrés du mois (pour coloration du calendrier)
    debut_mois = date_appel.replace(day=1)
    if debut_mois.month == 12:
        fin_mois = debut_mois.replace(year=debut_mois.year + 1, month=1, day=1) - datetime.timedelta(days=1)
    else:
        fin_mois = debut_mois.replace(month=debut_mois.month + 1, day=1) - datetime.timedelta(days=1)

    jours_non_ouvres_mois = set(
        JourNonOuvre.objects.filter(
            etablissement=etab, date__gte=debut_mois, date__lte=fin_mois
        ).values_list('date', flat=True)
    )
    # Ajouter dimanches du mois
    d = debut_mois
    while d <= fin_mois:
        if d.weekday() == 6:
            jours_non_ouvres_mois.add(d)
        d += datetime.timedelta(days=1)

    jours_non_ouvres_str = [j.isoformat() for j in jours_non_ouvres_mois]

    return render(request, "eleves/appel_presences.html", {
        "classes": classes,
        "classe": classe,
        "date_appel": date_appel,
        "eleves_data": eleves_data,
        "appel_fait": appel_fait,
        "annee": annee,
        "classe_id": classe_id,
        "today": timezone.now().date(),
        "jour_non_ouvre": jour_non_ouvre,
        "motif_non_ouvre": motif_non_ouvre,
        "jours_non_ouvres_str": jours_non_ouvres_str,
    })


# ══════════════════════════════════════════════════════════════
@login_required
@role_required(['admin', 'super_admin', 'secretariat', 'surveillant'])
@req
def gestion_jours_non_ouvres(request):
    """Liste + déclaration des jours non ouvrés."""
    etab = request.etablissement
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
    classes = get_classes_actives(etab, annee, user=request.user) if annee else []

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "declarer":
            date_str  = request.POST.get("date", "").strip()
            type_jour = request.POST.get("type_jour", "ferie")
            motif     = request.POST.get("motif", "").strip()
            classe_id = request.POST.get("classe_id") or None

            if not date_str or not motif:
                messages.error(request, "La date et le motif sont obligatoires.")
            else:
                try:
                    date_j = datetime.date.fromisoformat(date_str)
                    if date_j.weekday() == 6:
                        messages.warning(request, "Le dimanche est automatiquement chômé, pas besoin de le déclarer.")
                    else:
                        classe_obj = None
                        if classe_id:
                            classe_obj = get_object_or_404(Classe, pk=classe_id, etablissement=etab)
                        JourNonOuvre.objects.update_or_create(
                            etablissement=etab,
                            date=date_j,
                            classe=classe_obj,
                            defaults={
                                'type_jour': type_jour,
                                'motif': motif,
                                'annee': annee,
                                'declare_par': request.user,
                            }
                        )
                        portee = f"Classe {classe_obj.nom}" if classe_obj else "Tout l'établissement"
                        messages.success(request, f"✅ Jour non ouvré enregistré : {date_j.strftime('%d/%m/%Y')} — {motif} ({portee})")
                except Exception as e:
                    messages.error(request, f"Erreur : {e}")

        elif action == "supprimer":
            jour_id = request.POST.get("jour_id")
            try:
                jour = JourNonOuvre.objects.get(pk=jour_id, etablissement=etab)
                info = f"{jour.date.strftime('%d/%m/%Y')} — {jour.motif}"
                jour.delete()
                messages.success(request, f"✅ Supprimé : {info}")
            except JourNonOuvre.DoesNotExist:
                messages.error(request, "Jour introuvable.")

        return redirect('gestion_jours_non_ouvres')

    # Récupérer les jours : 60 jours en arrière + à venir
    depuis = timezone.now().date() - datetime.timedelta(days=60)
    jours = JourNonOuvre.objects.filter(
        etablissement=etab, date__gte=depuis
    ).select_related('classe', 'declare_par').order_by('date')

    return render(request, "eleves/jours_non_ouvres.html", {
        "jours": jours,
        "classes": classes,
        "annee": annee,
        "today": timezone.now().date(),
        "types": JourNonOuvre.TYPES,
    })


# ══════════════════════════════════════════════════════════════
@login_required
@role_required(['admin', 'super_admin', 'secretariat', 'surveillant', 'enseignant'])
@req
def historique_presences(request):
    etab = request.etablissement
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
    classes = get_classes_actives(etab, annee, user=request.user) if annee else []
    classe_id = request.GET.get("classe")
    mois = request.GET.get("mois", timezone.now().strftime("%Y-%m"))
    presences = []; classe = None; stats = {}
    if classe_id:
        classe = get_object_or_404(Classe, pk=classe_id, etablissement=etab)
        try:
            am, mn = mois.split("-")
            presences = Presence.objects.filter(
                classe=classe, date__year=am, date__month=mn
            ).select_related("eleve").order_by("-date", "eleve__nom")
            stats = {
                "total": presences.count(),
                "presents": presences.filter(statut="present").count(),
                "absents": presences.filter(statut="absent").count(),
                "retards": presences.filter(statut="retard").count(),
            }
        except Exception:
            pass
    return render(request, "eleves/historique_presences.html", {
        "classes": classes, "classe": classe, "classe_id": classe_id,
        "presences": presences, "mois": mois, "stats": stats,
    })


# ══════════════════════════════════════════════════════════════
@login_required
@req
def fiche_absences_eleve(request, eleve_pk):
    etab = request.etablissement
    eleve = get_object_or_404(Eleve, pk=eleve_pk, etablissement=etab)
    presences = Presence.objects.filter(eleve=eleve).order_by("-date")
    stats = {
        "total": presences.count(),
        "absents": presences.filter(statut="absent").count(),
        "retards": presences.filter(statut="retard").count(),
        "justifies": presences.filter(statut="justifie").count(),
    }
    return render(request, "eleves/fiche_absences.html", {
        "eleve": eleve, "presences": presences, "stats": stats,
        "inscription": eleve.get_inscription_active(),
    })
