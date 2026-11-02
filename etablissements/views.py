
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


# ── Helpers de validation des saisies enseignant ─────────────────────────────────────────────
PHOTO_MAX_OCTETS = 2 * 1024 * 1024  # 2 Mo (même limite que côté navigateur)
PHOTO_TYPES = ("image/jpeg", "image/png", "image/webp")
PHOTO_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


def _valider_photo(fichier):
    """Contrôle serveur strict de l'image (taille, extension, MIME, et structure image via Pillow)."""
    if not fichier:
        return None
    if fichier.size > PHOTO_MAX_OCTETS:
        return "L'image ne doit pas dépasser 2 Mo."
    nom = (getattr(fichier, "name", "") or "").lower()
    if not any(nom.endswith(ext) for ext in PHOTO_EXTENSIONS):
        return "Extension de fichier non autorisée (JPG, JPEG, PNG ou WEBP uniquement)."
    ct = getattr(fichier, "content_type", "") or ""
    if ct and ct not in PHOTO_TYPES:
        return "Format d'image non supporté (JPG, PNG ou WEBP)."
    try:
        from PIL import Image
        fichier.seek(0)
        img = Image.open(fichier)
        img.verify()
        if (img.format or "").upper() not in ("JPEG", "PNG", "WEBP"):
            return "Contenu du fichier image invalide (JPG, PNG ou WEBP attendu)."
        fichier.seek(0)
    except Exception:
        return "Le fichier téléversé n'est pas une image valide."
    return None


def _lire_champs_pro(request):
    """Lit et valide salaire / date d'embauche.
    Retourne (salaire, date_embauche, erreurs). Évite les erreurs 500 quand
    une valeur invalide est envoyée (le type=number/date du navigateur se contourne)."""
    from decimal import Decimal, InvalidOperation
    from datetime import date
    erreurs = []

    sal_brut = (request.POST.get("salaire") or "").strip().replace(" ", "")
    salaire = None
    if sal_brut:
        try:
            salaire = Decimal(sal_brut)
            if salaire < 0 or salaire != salaire.to_integral_value():
                raise InvalidOperation
        except InvalidOperation:
            erreurs.append("Salaire invalide (nombre entier positif attendu).")
            salaire = None

    de_brut = (request.POST.get("date_embauche") or "").strip()
    date_embauche = None
    if de_brut:
        try:
            date_embauche = date.fromisoformat(de_brut)
        except ValueError:
            erreurs.append("Date d'embauche invalide.")

    return salaire, date_embauche, erreurs


def req_gestion_enseignants(fn):
    """Comme @req mais restreint la gestion complète d'enseignant
    (creer/modifier/affecter) aux roles admin/directeur/secretariat uniquement.
    Whitelist explicite : tout role non liste est refuse par defaut."""
    ROLES_AUTORISES = ("super_admin", "admin", "secretariat")
    def w(request,*a,**k):
        if not request.etablissement: return redirect("dashboard")
        if request.user.role not in ROLES_AUTORISES:
            if request.user.role == "comptable":
                messages.error(request, "Accès réservé à la gestion administrative. Utilisez la vue Salaires.")
                return redirect("enseignants_comptable")
            messages.error(request, "Accès réservé à l'administration de l'établissement.")
            return redirect("dashboard")
        return fn(request,*a,**k)
    w.__name__=fn.__name__; return w

@login_required
@req
def liste_enseignants(request):
    # Les comptables ont leur propre vue dédiée
    if request.user.role == 'comptable':
        from django.urls import reverse
        from django.shortcuts import redirect as redir
        from urllib.parse import urlencode
        q = request.GET.get('q', '')
        return redir(reverse('enseignants_comptable') + ('?' + urlencode({'q': q}) if q else ''))
    if request.user.role not in ('admin', 'super_admin', 'secretariat'):
        messages.error(request, "Accès réservé à l'administration de l'établissement.")
        return redirect("dashboard")
    etab = request.etablissement
    ens = Enseignant.objects.filter(etablissement=etab).select_related("user")
    q = request.GET.get("q","")
    if q:
        from django.db.models import Q
        ens = ens.filter(Q(user__first_name__icontains=q)|Q(user__last_name__icontains=q))
    return render(request,"etablissements/liste_enseignants.html",{"enseignants":ens,"q":q,"total":ens.count()})

@login_required
@req_gestion_enseignants
def detail_enseignant(request,pk):
    etab = request.etablissement
    ens = get_object_or_404(Enseignant,pk=pk,etablissement=etab)
    annee = AnneeScolaire.objects.filter(etablissement=etab,is_active=True).first()
    affs = AffectationMatiere.objects.filter(enseignant=ens,annee=annee).select_related("matiere","classe__niveau") if annee else []
    return render(request,"etablissements/detail_enseignant.html",{"enseignant":ens,"affectations":affs,"annee":annee})

@login_required
@req_gestion_enseignants
def ajouter_enseignant(request):
    etab = request.etablissement
    if request.method=="POST":
        prenom=request.POST.get("prenom","").strip(); nom=request.POST.get("nom","").strip()
        username=request.POST.get("username","").strip(); password=request.POST.get("password","").strip()
        spec=request.POST.get("specialite","").strip(); diplome=request.POST.get("diplome","").strip()
        sal, de, erreurs_pro = _lire_champs_pro(request)
        photo = request.FILES.get('photo')
        erreur_photo = _valider_photo(photo)
        if not username or not nom:
            messages.error(request,"Nom et identifiant obligatoires.")
        elif not password:
            messages.error(request,"Le mot de passe est obligatoire.")
        elif User.objects.filter(username=username).exists():
            messages.error(request,f"Identifiant {username} deja utilise.")
        elif erreurs_pro or erreur_photo:
            for err in erreurs_pro + ([erreur_photo] if erreur_photo else []):
                messages.error(request, err)
        else:
            # Valider le mot de passe avec les validators Django (AUTH_PASSWORD_VALIDATORS :
            # longueur minimale, mots de passe courants, similarité, numérique).
            # Un User temporaire (non sauvegardé) permet le contrôle de similarité.
            from django.contrib.auth.password_validation import validate_password
            from django.core.exceptions import ValidationError
            from django.db import transaction
            try:
                validate_password(password, user=User(username=username, first_name=prenom, last_name=nom))
            except ValidationError as e:
                for err in e.messages:
                    messages.error(request, err)
            else:
                # Atomique : pas de compte User orphelin si la création de l'Enseignant échoue
                with transaction.atomic():
                    u=User.objects.create_user(username,"",password,first_name=prenom,last_name=nom,role="enseignant",etablissement=etab)
                    if photo:
                        u.photo = photo
                        u.save()
                    ens=Enseignant.objects.create(user=u,etablissement=etab,specialite=spec,diplome=diplome,date_embauche=de,salaire=sal)
                messages.success(request,f"Enseignant {ens.nom_complet} cree.")
                return redirect("detail_enseignant",pk=ens.pk)
        # Erreur : ré-afficher le formulaire avec les valeurs saisies
        # (le mot de passe et la photo ne sont volontairement pas renvoyés)
        return render(request,"etablissements/ajouter_enseignant.html",{"saisie": request.POST})
    return render(request,"etablissements/ajouter_enseignant.html",{})

@login_required
@req_gestion_enseignants
def modifier_enseignant(request,pk):
    etab = request.etablissement
    ens = get_object_or_404(Enseignant,pk=pk,etablissement=etab)
    if request.method=="POST":
        u=ens.user
        # ── 1. Lecture + validation de TOUT avant de modifier quoi que ce soit ──
        prenom = request.POST.get("prenom", "").strip()
        nom = request.POST.get("nom", "").strip()
        statut = request.POST.get("statut", ens.statut)
        pw = request.POST.get("password", "").strip()
        photo = request.FILES.get('photo')
        sal, de, erreurs = _lire_champs_pro(request)

        if not nom:
            erreurs.append("Le nom est obligatoire.")
        if statut not in dict(Enseignant.STATUTS):
            erreurs.append("Statut invalide.")
        erreur_photo = _valider_photo(photo)
        if erreur_photo:
            erreurs.append(erreur_photo)
        if pw:
            # Valider via les validators Django (longueur minimale définie dans settings)
            from django.contrib.auth.password_validation import validate_password
            from django.core.exceptions import ValidationError
            try:
                validate_password(pw, user=u)
            except ValidationError as e:
                erreurs.extend(e.messages)

        if erreurs:
            for err in erreurs:
                messages.error(request, err)
            # Re-afficher le formulaire avec les valeurs saisies (rien n'est perdu ni sauvegardé)
            return render(request, "etablissements/modifier_enseignant.html",
                          {"enseignant": ens, "saisie": request.POST})

        # ── 2. Application des modifications ──
        from django.db import transaction
        u.first_name = prenom
        u.last_name = nom
        u.email = request.POST.get("email", "").strip()
        u.telephone = request.POST.get("telephone", "").strip()
        if pw:
            u.set_password(pw)
        if photo:
            u.photo = photo
        # Statut « inactif » → compte bloqué (Django refuse la connexion des
        # comptes is_active=False et déconnecte une session déjà ouverte).
        # « actif » / « conge » → compte autorisé.
        ancien_actif = u.is_active
        u.is_active = (statut != "inactif")
        with transaction.atomic():
            u.save()
            ens.specialite=request.POST.get("specialite","").strip(); ens.diplome=request.POST.get("diplome","").strip()
            ens.statut=statut; ens.salaire=sal; ens.date_embauche=de
            ens.save()
        messages.success(request,f"{ens.nom_complet} mis a jour.")
        if ancien_actif and not u.is_active:
            messages.warning(request, "Compte désactivé : cet enseignant ne peut plus se connecter.")
        elif not ancien_actif and u.is_active:
            messages.info(request, "Compte réactivé : cet enseignant peut de nouveau se connecter.")
        return redirect("detail_enseignant",pk=ens.pk)
    return render(request,"etablissements/modifier_enseignant.html",{"enseignant":ens})

@login_required
@req_gestion_enseignants
def affecter_matiere(request,pk):
    etab=request.etablissement
    ens=get_object_or_404(Enseignant,pk=pk,etablissement=etab)
    annee=AnneeScolaire.objects.filter(etablissement=etab,is_active=True).first()
    classes=get_classes_actives(etab, annee, user=request.user) if annee else []
    matieres=Matiere.objects.filter(etablissement=etab,is_conduite=False)
    if request.method=="POST":
        c_id=request.POST.get("classe"); m_id=request.POST.get("matiere")
        # Sécurité multi-établissement : la classe et la matière doivent appartenir
        # à cet établissement (et la classe aux classes actives visibles).
        classe = next((c for c in classes if str(c.pk) == str(c_id)), None)
        matiere = matieres.filter(pk=m_id).first() if (m_id or "").isdigit() else None
        try:
            h = int(request.POST.get("heures_semaine", 2))
            if not 1 <= h <= 40:
                raise ValueError
        except (TypeError, ValueError):
            messages.error(request, "Nombre d'heures invalide (entre 1 et 40).")
            return redirect("affecter_matiere", pk=ens.pk)
        if not annee:
            messages.error(request, "Aucune année scolaire active.")
        elif not classe or not matiere:
            messages.error(request, "Classe ou matière invalide.")
        else:
            _,created=AffectationMatiere.objects.get_or_create(
                enseignant=ens,classe=classe,matiere=matiere,annee=annee,defaults={"heures_semaine":h})
            messages.success(request,"Affectation ajoutee." if created else "Deja existante.")
        return redirect("detail_enseignant",pk=ens.pk)
    return render(request,"etablissements/affecter_matiere.html",{"enseignant":ens,"classes":classes,"matieres":matieres,"annee":annee})
