from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import ModeleDocument

def req_admin(fn):
    def w(request, *a, **k):
        if not request.user.is_admin or not request.etablissement:
            return redirect("dashboard")
        return fn(request, *a, **k)
    w.__name__ = fn.__name__; return w

def _sauvegarder_modele(request, modele):
    for f in ["nom","ligne1_gauche","ligne2_gauche","ligne3_gauche","ligne1_droite","ligne2_droite","ligne3_droite","nom_etablissement_custom","titre_document","couleur_titre_bg","couleur_titre_texte","couleur_tableau_header","couleur_bordure","police","label_signature_gauche","label_signature_droite","texte_pied_page","couleur_accent_recu","format_recu","contenu_personnalise","entete_personnalise","pied_personnalise"]:
        v = request.POST.get(f)
        if v is not None: setattr(modele, f, v)
    for f in ["taille_police","note_max_classe","note_max_compo"]:
        v = request.POST.get(f)
        if v and v.strip().isdigit(): setattr(modele, f, int(v))
    for f in ["afficher_logo","afficher_adresse","afficher_telephone","col_moy_classe","col_moy_compo","col_moyenne_finale","col_coefficient","col_moy_coeffic","col_appreciation","afficher_moy_premier","afficher_rang","afficher_appre_directeur","afficher_date","is_actif"]:
        setattr(modele, f, f in request.POST)
    modele.save()

def _defaults(modele, td, etab):
    modele.ligne1_gauche = etab.nom; modele.ligne1_droite = "Republique du Mali"
    modele.ligne2_droite = "Un Peuple — Un But — Une Foi"
    if td=="bulletin":
        modele.titre_document="BULLETIN DE NOTES"; modele.couleur_titre_bg="#555555"
        modele.label_signature_gauche="Le Directeur"; modele.label_signature_droite="Le Parent ou Tuteur"
        modele.afficher_rang=True; modele.afficher_moy_premier=True; modele.afficher_appre_directeur=True
        modele.col_moy_classe=True; modele.col_moy_compo=True; modele.col_moyenne_finale=True
        modele.col_coefficient=True; modele.col_moy_coeffic=True; modele.col_appreciation=True
    elif td=="recu":
        modele.titre_document="RECU DE PAIEMENT"; modele.couleur_titre_bg="#1565C0"
        modele.couleur_accent_recu="#FF6F00"; modele.format_recu="A5"
    elif td=="certificat":
        modele.titre_document="CERTIFICAT DE SCOLARITE"; modele.couleur_titre_bg="#1565C0"
        modele.ligne1_gauche="Republique du Mali"; modele.ligne2_gauche="Ministere de l'Education Nationale"
        modele.label_signature_gauche="Le Directeur"; modele.label_signature_droite="Lu et approuve"
    elif td=="attestation":
        modele.titre_document="ATTESTATION DE FREQUENTATION"; modele.couleur_titre_bg="#1565C0"
        modele.label_signature_gauche="Le Directeur"
    elif td=="carte_scolaire":
        modele.titre_document="CARTE SCOLAIRE"; modele.couleur_titre_bg="#0D47A1"
        modele.couleur_accent_recu="#1565C0"
    elif td=="releve_notes":
        modele.titre_document="RELEVE DE NOTES"; modele.couleur_titre_bg="#2E7D32"
        modele.label_signature_gauche="Le Directeur"

@login_required
@req_admin
def liste_modeles(request):
    etab = request.etablissement
    modeles = ModeleDocument.objects.filter(etablissement=etab).order_by("type_document","nom")
    return render(request, "etablissements/modeles/liste.html", {"modeles":modeles,"types":ModeleDocument.TYPES})

@login_required
@req_admin
def creer_modele(request, type_doc=None):
    etab = request.etablissement
    if request.method=="POST":
        nom = request.POST.get("nom","").strip()
        td  = request.POST.get("type_document", type_doc or "bulletin")
        if not nom: messages.error(request,"Nom obligatoire.")
        else:
            modele = ModeleDocument(etablissement=etab, type_document=td, nom=nom)
            _defaults(modele, td, etab); modele.save()
            _sauvegarder_modele(request, modele)
            messages.success(request, f"Modele '{nom}' cree.")
            return redirect("modifier_modele", pk=modele.pk)
    return render(request, "etablissements/modeles/form.html", {
        "mode":"creer","types":ModeleDocument.TYPES,
        "type_doc_initial":type_doc or "bulletin","etab":etab,"modele":None})

@login_required
@req_admin
def modifier_modele(request, pk):
    etab = request.etablissement
    modele = get_object_or_404(ModeleDocument, pk=pk, etablissement=etab)
    if request.method=="POST":
        if request.POST.get("action")=="supprimer":
            modele.delete(); messages.success(request,"Modele supprime.")
            return redirect("liste_modeles")
        _sauvegarder_modele(request, modele)
        messages.success(request, f"'{modele.nom}' mis a jour.")
        return redirect("modifier_modele", pk=modele.pk)
    return render(request, "etablissements/modeles/form.html", {
        "mode":"modifier","modele":modele,"types":ModeleDocument.TYPES,"etab":etab,
        "type_doc_initial": modele.type_document})

@login_required
@req_admin
def activer_modele(request, pk):
    etab = request.etablissement
    m = get_object_or_404(ModeleDocument, pk=pk, etablissement=etab)
    ModeleDocument.objects.filter(etablissement=etab, type_document=m.type_document).update(is_actif=False)
    m.is_actif=True; m.save()
    messages.success(request,f"Modele '{m.nom}' active."); return redirect("liste_modeles")

@login_required
@req_admin
def apercu_modele(request, pk):
    from django.utils import timezone
    import random
    etab = request.etablissement
    modele = get_object_or_404(ModeleDocument, pk=pk, etablissement=etab)

    class Obj:
        def __init__(self,**kw): [setattr(self,k,v) for k,v in kw.items()]

    niv=Obj(nom="Second Cycle"); cl=Obj(nom="9eme Annee",niveau=niv); insc=Obj(classe=cl)
    an=Obj(libelle="2024-2025"); per=Obj(libelle="1er Trimestre",annee=an)
    el=Obj(nom="DAGNON",prenom="Harouna",matricule="EFBT-2024-0042",
           date_naissance=timezone.now().date(),lieu_naissance="Bamako",
           sexe="M",photo=None,age=14,
           tuteur=Obj(telephone="+223 76 11 22 33"),
           get_inscription_active=lambda:insc,nom_complet="DAGNON Harouna")

    lignes=[]
    for nom,coef,is_c in [("Mathematiques",3,False),("Francais",3,False),("Sciences",2,False),("Anglais",2,False),("EPS",1,False),("Conduite",1,True)]:
        m_obj=Obj(nom=nom,coefficient=coef,is_conduite=is_c); moy=round(random.uniform(9,18),2)
        if is_c:
            lignes.append({"matiere":m_obj,"moy_classe":None,"moy_compo":None,"note_conduite":round(random.uniform(12,18),1),"moyenne_finale":moy,"moy_coeffic":round(moy*coef,2),"appreciation":"Bien"})
        else:
            mc=round(moy+random.uniform(-2,2),2); mn=round(mc*2+random.uniform(-3,3),2)
            lignes.append({"matiere":m_obj,"moy_classe":mc,"moy_compo":mn,"note_conduite":None,"moyenne_finale":moy,"moy_coeffic":round(moy*coef,2),"appreciation":"Assez Bien"})

    tc=sum(l["matiere"].coefficient for l in lignes)
    tcoef=sum(l["moy_coeffic"] for l in lignes)
    moy_gen=round(tcoef/tc,2)

    templates_map={
        "bulletin":"notes/bulletin_eleve.html",
        "certificat":"core/docs/certificat_scolarite.html",
        "attestation":"core/docs/attestation_frequentation.html",
        "recu":"core/docs/recu_annuel.html",
        "carte_scolaire":"core/docs/carte_scolaire.html",
        "releve_notes":"notes/bulletin_eleve.html",
    }
    tmpl=templates_map.get(modele.type_document,"notes/bulletin_eleve.html")

    paiements_demo=[
        Obj(date_paiement=timezone.now(),type_frais=Obj(nom="Frais d'inscription"),
            get_mode_paiement_display=lambda:"Especes",montant=25000,reference="PAY-0001"),
        Obj(date_paiement=timezone.now(),type_frais=Obj(nom="Scolarite mensuelle"),
            get_mode_paiement_display=lambda:"Mobile Money",montant=15000,reference="PAY-0002"),
    ]

    return render(request, tmpl, {
        "eleve":el,"periode":per,"annee":an,"etab":etab,"modele":modele,"inscription":insc,
        "lignes":lignes,"moy_generale":moy_gen,"rang":3,"effectif":35,"moy_premier":17.5,
        "appre_directeur":"Tres Bien","today":timezone.now().date(),"is_apercu":True,
        "paiements":paiements_demo,"total":40000,"ref":"APER-DEMO-2025",
    })
