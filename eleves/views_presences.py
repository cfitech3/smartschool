
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count
from .models import Presence, Inscription, Eleve
from etablissements.models import Classe, AnneeScolaire
import datetime
from core.cycle_filter import get_cycles_actifs_ids, get_classes_actives, get_eleves_actifs, get_inscriptions_actives

def req(fn):
    def w(request,*a,**k):
        if not request.etablissement: return redirect("dashboard")
        return fn(request,*a,**k)
    w.__name__=fn.__name__; return w

@login_required
@req
def appel_presences(request):
    etab=request.etablissement
    annee=AnneeScolaire.objects.filter(etablissement=etab,is_active=True).first()
    classes=get_classes_actives(etab, annee) if annee else []
    classe_id=request.GET.get("classe"); date_str=request.GET.get("date",timezone.now().date().isoformat())
    try: date_appel=datetime.date.fromisoformat(date_str)
    except: date_appel=timezone.now().date()
    classe=None; eleves_data=[]; appel_fait=False
    if classe_id:
        classe=get_object_or_404(Classe,pk=classe_id,etablissement=etab)
        inscriptions=classe.inscriptions.filter(is_active=True).select_related("eleve").order_by("eleve__nom","eleve__prenom")
        pex={p.eleve_id:p for p in Presence.objects.filter(classe=classe,date=date_appel)}
        appel_fait=bool(pex)
        for insc in inscriptions:
            p=pex.get(insc.eleve.pk)
            eleves_data.append({"eleve":insc.eleve,"statut":p.statut if p else "present","motif":p.motif if p else "","presence_id":p.pk if p else None})
    if request.method=="POST" and classe_id:
        classe=get_object_or_404(Classe,pk=classe_id,etablissement=etab)
        saved=0
        for insc in classe.inscriptions.filter(is_active=True).select_related("eleve"):
            st=request.POST.get(f"statut_{insc.eleve.pk}","present"); mo=request.POST.get(f"motif_{insc.eleve.pk}","")
            Presence.objects.update_or_create(eleve=insc.eleve,classe=classe,date=date_appel,
                defaults={"statut":st,"motif":mo,"enregistre_par":request.user}); saved+=1
        messages.success(request,f"Appel enregistre : {saved} eleve(s) — {classe.nom} — {date_appel.strftime("%d/%m/%Y")}")
        return redirect(f"{request.path}?classe={classe_id}&date={date_appel}")
    return render(request,"eleves/appel_presences.html",{"classes":classes,"classe":classe,"date_appel":date_appel,"eleves_data":eleves_data,"appel_fait":appel_fait,"annee":annee,"classe_id":classe_id,"today":timezone.now().date()})

@login_required
@req
def historique_presences(request):
    etab=request.etablissement; annee=AnneeScolaire.objects.filter(etablissement=etab,is_active=True).first()
    classes=get_classes_actives(etab, annee) if annee else []
    classe_id=request.GET.get("classe"); mois=request.GET.get("mois",timezone.now().strftime("%Y-%m"))
    presences=[]; classe=None; stats={}
    if classe_id:
        classe=get_object_or_404(Classe,pk=classe_id,etablissement=etab)
        try:
            am,mn=mois.split("-")
            presences=Presence.objects.filter(classe=classe,date__year=am,date__month=mn).select_related("eleve").order_by("-date","eleve__nom")
            stats={"total":presences.count(),"presents":presences.filter(statut="present").count(),"absents":presences.filter(statut="absent").count(),"retards":presences.filter(statut="retard").count()}
        except: pass
    return render(request,"eleves/historique_presences.html",{"classes":classes,"classe":classe,"classe_id":classe_id,"presences":presences,"mois":mois,"stats":stats})

@login_required
@req
def fiche_absences_eleve(request,eleve_pk):
    etab=request.etablissement
    eleve=get_object_or_404(Eleve,pk=eleve_pk,etablissement=etab)
    presences=Presence.objects.filter(eleve=eleve).order_by("-date")
    stats={"total":presences.count(),"absents":presences.filter(statut="absent").count(),"retards":presences.filter(statut="retard").count(),"justifies":presences.filter(statut="justifie").count()}
    return render(request,"eleves/fiche_absences.html",{"eleve":eleve,"presences":presences,"stats":stats,"inscription":eleve.get_inscription_active()})
