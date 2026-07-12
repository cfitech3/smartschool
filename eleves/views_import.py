import openpyxl
from datetime import datetime
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.db import transaction
from django.contrib.auth.hashers import make_password
from eleves.models import Eleve, Tuteur, Inscription
from etablissements.models import Classe, AnneeScolaire
from accounts.models import User
import unicodedata

def normalize_username(name):
    """Génère un username propre sans accents ni espaces."""
    n = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('utf-8')
    return n.lower().replace(" ", "")

@login_required
def telecharger_modele_excel(request):
    if not request.user.role in ['admin', 'super_admin', 'secretariat']:
        messages.error(request, "Accès refusé.")
        return redirect('dashboard')
        
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Import Eleves"
    
    # En-têtes
    headers = [
        "Nom de l'élève", "Prénom de l'élève", "Sexe (M/F)", 
        "Date Naissance (JJ/MM/AAAA)", "Nom de la Classe",
        "Nom du Parent", "Prénom du Parent", "Téléphone Parent"
    ]
    ws.append(headers)
    
    # Styliser la première ligne
    for cell in ws[1]:
        cell.font = openpyxl.styles.Font(bold=True)
        cell.fill = openpyxl.styles.PatternFill(start_color="1E88E5", end_color="1E88E5", fill_type="solid")
        cell.font = openpyxl.styles.Font(color="FFFFFF", bold=True)
        
    # Ajuster la largeur des colonnes
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(cell.value)
            except:
                pass
        ws.column_dimensions[column].width = max_length + 5

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="modele_import_eleves.xlsx"'
    wb.save(response)
    return response

@login_required
def import_eleves_excel(request):
    if not request.user.role in ['admin', 'super_admin', 'secretariat']:
        messages.error(request, "Accès refusé.")
        return redirect('dashboard')

    etab = request.etablissement
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()

    if not annee:
        messages.error(request, "Aucune année scolaire active n'a été trouvée.")
        return redirect('liste_eleves')

    if request.method == "POST":
        excel_file = request.FILES.get("fichier_excel")
        if not excel_file:
            messages.error(request, "Veuillez fournir un fichier Excel.")
            return redirect('import_eleves_excel')
            
        if not excel_file.name.endswith('.xlsx'):
            messages.error(request, "Le fichier doit être au format .xlsx.")
            return redirect('import_eleves_excel')

        try:
            wb = openpyxl.load_workbook(excel_file, data_only=True)
            ws = wb.active
            
            nb_crees = 0
            nb_erreurs = 0
            erreurs_details = []

            for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                if not any(row):  # Ligne vide
                    continue
                    
                try:
                    # Extraction (en gérant les cases vides)
                    nom_e = str(row[0] or "").strip()
                    prenom_e = str(row[1] or "").strip()
                    sexe = str(row[2] or "M").strip().upper()
                    date_naiss = row[3]
                    nom_classe = str(row[4] or "").strip()
                    nom_p = str(row[5] or "").strip()
                    prenom_p = str(row[6] or "").strip()
                    tel_p = str(row[7] or "").strip()

                    if not nom_e or not prenom_e or not nom_classe:
                        raise ValueError("Nom, Prénom et Classe de l'élève sont obligatoires.")

                    # Formatage Date
                    if isinstance(date_naiss, datetime):
                        dob = date_naiss.date()
                    else:
                        try:
                            dob = datetime.strptime(str(date_naiss).strip()[:10], "%d/%m/%Y").date()
                        except:
                            dob = None # Toléré

                    # 1. Récupérer ou créer le Parent (Tuteur)
                    tuteur = None
                    if nom_p and tel_p:
                        tuteur = Tuteur.objects.filter(telephone1=tel_p).first()
                        if not tuteur:
                            base_username = f"p.{normalize_username(nom_p)}.{normalize_username(prenom_p)}"
                            username = base_username
                            counter = 1
                            while User.objects.filter(username=username).exists():
                                username = f"{base_username}{counter}"
                                counter += 1
                                
                            user_parent = User.objects.create(
                                username=username,
                                first_name=prenom_p,
                                last_name=nom_p,
                                role='parent',
                                password=make_password("pass123"),
                                is_active=True
                            )
                            tuteur = Tuteur.objects.create(
                                user_compte=user_parent,
                                nom=nom_p,
                                prenom=prenom_p,
                                telephone1=tel_p
                            )

                    # 2. Vérifier la Classe
                    classe = Classe.objects.filter(etablissement=etab, annee=annee, nom__iexact=nom_classe).first()
                    if not classe:
                        raise ValueError(f"La classe '{nom_classe}' n'existe pas dans l'année active.")

                    # 3. Créer l'Élève
                    with transaction.atomic():
                        base_eleve_usr = f"e.{normalize_username(nom_e)}.{normalize_username(prenom_e)}"
                        e_username = base_eleve_usr
                        e_counter = 1
                        while User.objects.filter(username=e_username).exists():
                            e_username = f"{base_eleve_usr}{e_counter}"
                            e_counter += 1
                            
                        user_eleve = User.objects.create(
                            username=e_username,
                            first_name=prenom_e,
                            last_name=nom_e,
                            role='eleve',
                            password=make_password("pass123"),
                            is_active=True,
                            etablissement=etab
                        )
                        
                        eleve = Eleve.objects.create(
                            etablissement=etab,
                            user_compte=user_eleve,
                            matricule=f"E{etab.pk}{annee.pk}{Eleve.objects.count()+1}",
                            nom=nom_e,
                            prenom=prenom_e,
                            sexe='M' if sexe.startswith('M') else 'F',
                            date_naissance=dob,
                            tuteur=tuteur
                        )
                        
                        # 4. Inscription
                        Inscription.objects.create(
                            eleve=eleve,
                            classe=classe,
                            annee=annee,
                            statut='actif'
                        )
                    nb_crees += 1

                except Exception as e:
                    nb_erreurs += 1
                    erreurs_details.append(f"Ligne {row_idx} ({nom_e} {prenom_e}) : {str(e)}")

            if nb_crees > 0:
                messages.success(request, f"✅ Import réussi : {nb_crees} élève(s) ajouté(s).")
            if nb_erreurs > 0:
                messages.error(request, f"⚠️ {nb_erreurs} ligne(s) ignorée(s) (voir détails plus bas).")
                for err in erreurs_details[:10]:
                    messages.warning(request, err)

            return redirect('liste_eleves')

        except Exception as e:
            messages.error(request, f"Erreur lors de la lecture du fichier : {str(e)}")
            return redirect('import_eleves_excel')

    return render(request, 'eleves/import_excel.html')
