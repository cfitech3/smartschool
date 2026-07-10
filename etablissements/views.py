
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Enseignant, AffectationMatiere, AnneeScolaire, Classe
from notes.models import Matiere
from accounts.models import User
from core.cycle_filter import get_cycles_actifs_ids, get_classes_actives, get_eleves_actifs, get_inscriptions_actives

def req(fn):
    def w(request,*a,**k):
        if not request.etablissement: return redirect("dashboard")
        return fn(request,*a,**k)
    w.__name__=fn.__name__; return w

@login_required
@req
def liste_enseignants(request):
    etab = request.etablissement
    ens = Enseignant.objects.filter(etablissement=etab).select_related("user")
    q = request.GET.get("q","")
    if q:
        from django.db.models import Q
        ens = ens.filter(Q(user__first_name__icontains=q)|Q(user__last_name__icontains=q))
    return render(request,"etablissements/liste_enseignants.html",{"enseignants":ens,"q":q,"total":ens.count()})

@login_required
@req
def detail_enseignant(request,pk):
    etab = request.etablissement
    ens = get_object_or_404(Enseignant,pk=pk,etablissement=etab)
    annee = AnneeScolaire.objects.filter(etablissement=etab,is_active=True).first()
    affs = AffectationMatiere.objects.filter(enseignant=ens,annee=annee).select_related("matiere","classe__niveau") if annee else []
    return render(request,"etablissements/detail_enseignant.html",{"enseignant":ens,"affectations":affs,"annee":annee})

@login_required
@req
def ajouter_enseignant(request):
    etab = request.etablissement
    if request.method=="POST":
        prenom=request.POST.get("prenom","").strip(); nom=request.POST.get("nom","").strip()
        username=request.POST.get("username","").strip(); password=request.POST.get("password","admin123")
        spec=request.POST.get("specialite",""); diplome=request.POST.get("diplome","")
        sal=request.POST.get("salaire") or None; de=request.POST.get("date_embauche") or None
        if not username or not nom:
            messages.error(request,"Nom et identifiant obligatoires."); 
        elif User.objects.filter(username=username).exists():
            messages.error(request,f"Identifiant {username} deja utilise.")
        else:
            u=User.objects.create_user(username,"",password,first_name=prenom,last_name=nom,role="enseignant",etablissement=etab)
            ens=Enseignant.objects.create(user=u,etablissement=etab,specialite=spec,diplome=diplome,date_embauche=de,salaire=sal)
            messages.success(request,f"Enseignant {ens.nom_complet} cree.")
            return redirect("detail_enseignant",pk=ens.pk)
    return render(request,"etablissements/ajouter_enseignant.html",{})

@login_required
@req
def modifier_enseignant(request,pk):
    etab = request.etablissement
    ens = get_object_or_404(Enseignant,pk=pk,etablissement=etab)
    if request.method=="POST":
        u=ens.user; u.first_name=request.POST.get("prenom",u.first_name)
        u.last_name=request.POST.get("nom",u.last_name); u.email=request.POST.get("email","")
        u.telephone=request.POST.get("telephone","")
        pw=request.POST.get("password","").strip()
        if pw: u.set_password(pw)
        u.save()
        ens.specialite=request.POST.get("specialite",""); ens.diplome=request.POST.get("diplome","")
        ens.statut=request.POST.get("statut","actif"); ens.salaire=request.POST.get("salaire") or None
        ens.date_embauche=request.POST.get("date_embauche") or None; ens.save()
        messages.success(request,f"{ens.nom_complet} mis a jour."); return redirect("detail_enseignant",pk=ens.pk)
    return render(request,"etablissements/modifier_enseignant.html",{"enseignant":ens})

@login_required
@req
def affecter_matiere(request,pk):
    etab=request.etablissement
    ens=get_object_or_404(Enseignant,pk=pk,etablissement=etab)
    annee=AnneeScolaire.objects.filter(etablissement=etab,is_active=True).first()
    classes=get_classes_actives(etab, annee) if annee else []
    matieres=Matiere.objects.filter(etablissement=etab,is_conduite=False)
    if request.method=="POST":
        c_id=request.POST.get("classe"); m_id=request.POST.get("matiere"); h=request.POST.get("heures_semaine",2)
        if c_id and m_id and annee:
            _,created=AffectationMatiere.objects.get_or_create(
                enseignant=ens,classe_id=c_id,matiere_id=m_id,annee=annee,defaults={"heures_semaine":h})
            messages.success(request,"Affectation ajoutee." if created else "Deja existante.")
        return redirect("detail_enseignant",pk=ens.pk)
    return render(request,"etablissements/affecter_matiere.html",{"enseignant":ens,"classes":classes,"matieres":matieres,"annee":annee})
