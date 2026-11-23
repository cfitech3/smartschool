"""
Saisie de notes hors-ligne par fichier Excel (.xlsx) :
  1. Téléchargement d'une grille Excel pré-remplie (matricules, noms, notes existantes)
     pour le 1er cycle (Composition /10), 2e cycle & Lycée (NotePeriode /20+/40 ou direct /20),
     Conduite (/18) et Université LMD (NoteUE Session 1 & Rattrapage /20).
  2. Ré-importation sécurisée en un clic avec contrôle de barème, RBAC enseignant
     et journalisation dans LogModificationNote.
"""
from decimal import Decimal, InvalidOperation
import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect

from accounts.permissions import permission_required, require_etab, is_etab_superieur
from core.cycle_filter import get_classes_actives
from core.validators import safe_excel_value
from eleves.models import Inscription
from etablissements.models import AnneeScolaire, Classe, UEUniversite, AffectationMatiere
from .models import Matiere, Periode, NotePeriode, NoteUE, Composition, LogModificationNote
from .views_universite import _filtrer_ues_filiere


def _parse_dec(val, min_v, max_v):
    """Convertit une cellule Excel en Decimal borné entre min_v et max_v."""
    if val is None:
        return None
    s = str(val).strip().replace(',', '.')
    if s == '' or s in ('—', '-', 'None'):
        return None
    d = Decimal(str(round(float(s), 2)))
    if d < Decimal(str(min_v)) or d > Decimal(str(max_v)):
        raise ValueError(f"Valeur {d} hors barème [{min_v}..{max_v}]")
    return d


def _verifier_acces_enseignant_matiere(user, etab, annee, classe, matiere):
    """Vérifie qu'un enseignant a bien le droit de saisir dans cette classe/matière."""
    if not user.is_enseignant:
        return True
    aff_qs = AffectationMatiere.objects.filter(enseignant__user=user, annee=annee)
    if aff_qs.exists():
        return aff_qs.filter(classe=classe, matiere=matiere).exists()
    from .models import EmploiDuTemps
    return EmploiDuTemps.objects.filter(
        etablissement=etab, classe=classe, matiere=matiere, enseignant=user
    ).exists()


@login_required
@permission_required('notes')
@require_etab
def telecharger_modele_saisie_excel(request):
    """Génère et télécharge la grille Excel pré-remplie pour la saisie hors-ligne."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    etab = request.etablissement
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
    classes = get_classes_actives(etab, annee, user=request.user) if annee else Classe.objects.none()

    classe_id = request.GET.get('classe')
    periode_id = request.GET.get('periode')
    matiere_id = request.GET.get('matiere')
    numero = request.GET.get('numero')
    semestre = request.GET.get('semestre', '1')
    mode_lmd = request.GET.get('lmd') == '1'

    if not (classe_id and str(classe_id).isdigit()):
        messages.error(request, "Veuillez sélectionner une classe valide.")
        return redirect('saisie_notes_mali')
    classe = get_object_or_404(classes, pk=int(classe_id), etablissement=etab)
    inscriptions = list(
        Inscription.objects.filter(classe=classe, annee=annee, is_active=True)
        .select_related('eleve').order_by('eleve__nom', 'eleve__prenom')
    )
    eleves = [i.eleve for i in inscriptions]

    cycle = classe.niveau.cycle if (classe.niveau and classe.niveau.cycle) else None
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Saisie_Notes"

    bleu = PatternFill("solid", fgColor="1565C0")
    gris_clair = PatternFill("solid", fgColor="F1F5F9")
    jaune_saisie = PatternFill("solid", fgColor="FFFDE7")
    font_h = Font(bold=True, color="FFFFFF", size=11)
    font_b = Font(bold=True, size=10)
    thin = Side(style='thin', color="CBD5E1")
    brd = Border(left=thin, right=thin, top=thin, bottom=thin)

    # ── CAS 1 : UNIVERSITÉ (LMD) ─────────────────────────────────────────────
    if mode_lmd or (cycle and cycle.is_universite):
        if not is_etab_superieur(etab):
            messages.error(request, "Action réservée à l'enseignement supérieur.")
            return redirect('saisie_notes_mali')
        periode = get_object_or_404(Periode, pk=periode_id, etablissement=etab)
        sem_int = int(semestre) if str(semestre).isdigit() else 1
        ues = list(_filtrer_ues_filiere(
            UEUniversite.objects.filter(cycle=cycle, semestre=sem_int), classe
        ).order_by('code'))

        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=2 + len(ues) * 2)
        ws['A1'] = f"GRILLE DE SAISIE LMD HORS-LIGNE — {etab.nom.upper()} — {classe.nom} (Semestre {sem_int})"
        ws['A1'].font = Font(bold=True, size=13, color="1565C0")

        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=2 + len(ues) * 2)
        ws['A2'] = f"Période : {periode.libelle} | Barème : /20 | Ne modifiez pas la colonne Matricule."
        ws['A2'].font = Font(italic=True, size=10, color="475569")

        headers = ["Matricule", "Nom & Prénom"]
        for ue in ues:
            headers.append(f"{ue.code} — Session 1 (/20)")
            headers.append(f"{ue.code} — Rattrapage (/20)")

        for col_idx, h in enumerate(headers, 1):
            c = ws.cell(row=4, column=col_idx, value=h)
            c.font = font_h
            c.fill = bleu
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            c.border = brd
        ws.row_dimensions[4].height = 28

        notes_map = {
            (n.eleve_id, n.ue_id): n
            for n in NoteUE.objects.filter(classe=classe, periode=periode, ue__in=ues)
        }

        for r_idx, el in enumerate(eleves, 5):
            c1 = ws.cell(row=r_idx, column=1, value=safe_excel_value(el.matricule))
            c2 = ws.cell(row=r_idx, column=2, value=safe_excel_value(f"{el.nom} {el.prenom}"))
            c1.font = font_b
            c1.fill = gris_clair
            c2.fill = gris_clair
            c1.border = brd
            c2.border = brd
            col_c = 3
            for ue in ues:
                n_obj = notes_map.get((el.pk, ue.pk))
                cs1 = ws.cell(row=r_idx, column=col_c, value=float(n_obj.note) if (n_obj and n_obj.note is not None) else None)
                cratt = ws.cell(row=r_idx, column=col_c + 1, value=float(n_obj.note_rattrapage) if (n_obj and n_obj.note_rattrapage is not None) else None)
                for cell in (cs1, cratt):
                    cell.fill = jaune_saisie
                    cell.border = brd
                    cell.alignment = Alignment(horizontal="center")
                col_c += 2

        ws.column_dimensions['A'].width = 18
        ws.column_dimensions['B'].width = 28
        for col_i in range(3, 3 + len(ues) * 2):
            ws.column_dimensions[get_column_letter(col_i)].width = 18

        ws_meta = wb.create_sheet("_META")
        ws_meta.sheet_state = 'hidden'
        ws_meta.append(["mode", "lmd"])
        ws_meta.append(["classe_id", str(classe.pk)])
        ws_meta.append(["periode_id", str(periode.pk)])
        ws_meta.append(["semestre", str(sem_int)])
        ws_meta.append(["ues", ",".join(str(u.pk) for u in ues)])

        fname = f"Saisie_LMD_{classe.nom.replace(' ', '_')}_S{sem_int}.xlsx"

    # ── CAS 2 : SCOLAIRE (1er cycle, 2e cycle, Lycée, Conduite) ──────────────
    else:
        matiere = get_object_or_404(Matiere, pk=matiere_id, etablissement=etab)
        if not _verifier_acces_enseignant_matiere(request.user, etab, annee, classe, matiere):
            messages.error(request, "Vous n'êtes pas affecté à cette matière dans cette classe.")
            return redirect('saisie_notes_mali')

        is_premier_cycle = bool(cycle and cycle.is_premier_cycle and cycle.utilise_compositions_multiples)
        mode_calcul = cycle.mode_calcul if cycle else 'classique'

        if matiere.is_conduite:
            mode_scol = 'conduite'
            periode = get_object_or_404(Periode, pk=periode_id, etablissement=etab)
            cols_notes = ["Note Conduite (/18)"]
            notes_exist = {
                n.eleve_id: n for n in NotePeriode.objects.filter(classe=classe, periode=periode, matiere=matiere)
            }
            per_label = periode.libelle
        elif is_premier_cycle:
            mode_scol = 'premier_cycle'
            num_int = int(numero) if (numero and str(numero).isdigit()) else 1
            cols_notes = [f"Note Composition {num_int} (/10)"]
            notes_exist = {
                c.eleve_id: c for c in Composition.objects.filter(
                    classe=classe, annee=annee, matiere=matiere, numero=num_int
                )
            }
            per_label = f"Composition {num_int}"
        elif mode_calcul == 'direct':
            mode_scol = 'direct'
            periode = get_object_or_404(Periode, pk=periode_id, etablissement=etab)
            cols_notes = ["Note Directe (/20)"]
            notes_exist = {
                n.eleve_id: n for n in NotePeriode.objects.filter(classe=classe, periode=periode, matiere=matiere)
            }
            per_label = periode.libelle
        else:
            mode_scol = 'classique'
            periode = get_object_or_404(Periode, pk=periode_id, etablissement=etab)
            cols_notes = ["Moyenne Classe (/20)", "Note Composition (/40)"]
            notes_exist = {
                n.eleve_id: n for n in NotePeriode.objects.filter(classe=classe, periode=periode, matiere=matiere)
            }
            per_label = periode.libelle

        nb_cols = 2 + len(cols_notes)
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=nb_cols)
        ws['A1'] = f"GRILLE DE SAISIE HORS-LIGNE — {etab.nom.upper()} — {classe.nom} — {matiere.nom}"
        ws['A1'].font = Font(bold=True, size=13, color="1565C0")

        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=nb_cols)
        ws['A2'] = f"{per_label} | Coef : {matiere.coefficient} | Remplissez les colonnes jaunes puis ré-importez ce fichier."
        ws['A2'].font = Font(italic=True, size=10, color="475569")

        headers = ["Matricule", "Nom & Prénom"] + cols_notes
        for col_idx, h in enumerate(headers, 1):
            c = ws.cell(row=4, column=col_idx, value=h)
            c.font = font_h
            c.fill = bleu
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = brd
        ws.row_dimensions[4].height = 26

        for r_idx, el in enumerate(eleves, 5):
            c1 = ws.cell(row=r_idx, column=1, value=safe_excel_value(el.matricule))
            c2 = ws.cell(row=r_idx, column=2, value=safe_excel_value(f"{el.nom} {el.prenom}"))
            c1.font = font_b
            c1.fill = gris_clair
            c2.fill = gris_clair
            c1.border = brd
            c2.border = brd

            obj = notes_exist.get(el.pk)
            if mode_scol == 'conduite':
                vals = [float(obj.note_conduite) if (obj and obj.note_conduite is not None) else None]
            elif mode_scol == 'premier_cycle':
                vals = [float(obj.note) if (obj and obj.note is not None) else None]
            elif mode_scol == 'direct':
                vals = [float(obj.moyenne_finale) if (obj and obj.moyenne_finale is not None) else None]
            else:
                vals = [
                    float(obj.moy_classe) if (obj and obj.moy_classe is not None) else None,
                    float(obj.moy_compo) if (obj and obj.moy_compo is not None) else None,
                ]
            for offset, v in enumerate(vals):
                cell = ws.cell(row=r_idx, column=3 + offset, value=v)
                cell.fill = jaune_saisie
                cell.border = brd
                cell.alignment = Alignment(horizontal="center")

        ws.column_dimensions['A'].width = 18
        ws.column_dimensions['B'].width = 30
        ws.column_dimensions['C'].width = 24
        if len(cols_notes) > 1:
            ws.column_dimensions['D'].width = 24

        ws_meta = wb.create_sheet("_META")
        ws_meta.sheet_state = 'hidden'
        ws_meta.append(["mode", mode_scol])
        ws_meta.append(["classe_id", str(classe.pk)])
        ws_meta.append(["matiere_id", str(matiere.pk)])
        ws_meta.append(["periode_id", str(periode_id or '')])
        ws_meta.append(["numero", str(numero or '')])

        fname = f"Saisie_{classe.nom.replace(' ', '_')}_{matiere.nom.replace(' ', '_')}.xlsx"

    ws.freeze_panes = 'C5'
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    response = HttpResponse(
        buf.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


@login_required
@permission_required('notes')
@require_etab
def importer_notes_excel(request):
    """Importe un fichier Excel (.xlsx) de notes rempli hors-ligne."""
    import openpyxl

    if request.method != 'POST':
        return redirect('saisie_notes_mali')

    etab = request.etablissement
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
    classes = get_classes_actives(etab, annee, user=request.user) if annee else Classe.objects.none()

    classe_id = request.POST.get('classe')
    periode_id = request.POST.get('periode')
    matiere_id = request.POST.get('matiere')
    numero = request.POST.get('numero')
    semestre = request.POST.get('semestre', '1')
    session_mode = request.POST.get('session', 'normale')
    mode_lmd = request.POST.get('lmd') == '1'

    redirect_url = (
        f"/notes/universite/saisie/?classe={classe_id or ''}&periode={periode_id or ''}&semestre={semestre}&session={session_mode}"
        if mode_lmd else
        f"/notes/saisie/?classe={classe_id or ''}&periode={periode_id or ''}&numero={numero or ''}&matiere={matiere_id or ''}"
    )

    fichier = request.FILES.get('fichier_excel')
    if not fichier or not fichier.name.lower().endswith('.xlsx'):
        messages.error(request, "Veuillez sélectionner un fichier Excel valide (.xlsx).")
        return redirect(redirect_url)

    if not (classe_id and str(classe_id).isdigit()):
        messages.error(request, "Veuillez sélectionner une classe valide.")
        return redirect('saisie_notes_mali')
    classe = get_object_or_404(classes, pk=int(classe_id), etablissement=etab)
    inscriptions = Inscription.objects.filter(classe=classe, annee=annee, is_active=True).select_related('eleve')
    eleves_par_matricule = {
        (i.eleve.matricule or '').strip().upper(): i.eleve
        for i in inscriptions if i.eleve.matricule
    }

    try:
        wb = openpyxl.load_workbook(fichier, data_only=True)
    except Exception:
        messages.error(request, "Impossible de lire le fichier Excel. Vérifiez qu'il n'est pas corrompu.")
        return redirect(redirect_url)

    # Vérifier la feuille _META si présente pour empêcher l'import d'une autre classe/matière
    meta = {}
    if "_META" in wb.sheetnames:
        for row in wb["_META"].iter_rows(values_only=True):
            if row and len(row) >= 2 and row[0]:
                meta[str(row[0])] = str(row[1] or '')
        if meta.get('classe_id') and meta['classe_id'] != str(classe.pk):
            messages.error(request, "Ce fichier Excel correspond à une autre classe. Importation annulée.")
            return redirect(redirect_url)
        if not mode_lmd and meta.get('matiere_id') and meta['matiere_id'] != str(matiere_id):
            messages.error(request, "Ce fichier Excel correspond à une autre matière. Importation annulée.")
            return redirect(redirect_url)

    ws = wb["Saisie_Notes"] if "Saisie_Notes" in wb.sheetnames else wb.active
    cycle = classe.niveau.cycle if (classe.niveau and classe.niveau.cycle) else None

    nb_importees = 0
    erreurs = []

    with transaction.atomic():
        # ── IMPORT UNIVERSITÉ LMD ────────────────────────────────────────────
        if mode_lmd or (cycle and cycle.is_universite):
            periode = get_object_or_404(Periode, pk=periode_id, etablissement=etab)
            if not periode.peut_saisir and not request.user.is_admin:
                messages.error(request, "La saisie est clôturée pour cette période.")
                return redirect(redirect_url)

            sem_int = int(semestre) if str(semestre).isdigit() else 1
            ues = list(_filtrer_ues_filiere(
                UEUniversite.objects.filter(cycle=cycle, semestre=sem_int), classe
            ).order_by('code'))

            for r_idx, row in enumerate(ws.iter_rows(min_row=5, values_only=True), 5):
                if not row or not row[0]:
                    continue
                mat = str(row[0]).strip().upper()
                eleve = eleves_par_matricule.get(mat)
                if not eleve:
                    continue
                for idx_ue, ue in enumerate(ues):
                    col_s1 = 2 + idx_ue * 2
                    col_ratt = col_s1 + 1
                    raw_s1 = row[col_s1] if col_s1 < len(row) else None
                    raw_ratt = row[col_ratt] if col_ratt < len(row) else None
                    try:
                        val_s1 = _parse_dec(raw_s1, 0, 20)
                        val_ratt = _parse_dec(raw_ratt, 0, 20)
                    except (ValueError, InvalidOperation) as e:
                        erreurs.append(f"Ligne {r_idx} ({mat}, {ue.code}) : {e}")
                        continue

                    if val_s1 is None and val_ratt is None:
                        continue
                    exist = NoteUE.objects.filter(eleve=eleve, ue=ue, classe=classe, periode=periode).first()
                    if session_mode == 'rattrapage' and exist and exist.note is not None and float(exist.note) >= 10:
                        continue
                    if exist:
                        if session_mode != 'rattrapage' and val_s1 is not None:
                            exist.note = val_s1
                        if val_ratt is not None:
                            exist.note_rattrapage = val_ratt
                        exist.saisi_par = request.user
                        exist.save()
                    else:
                        NoteUE.objects.create(
                            eleve=eleve, ue=ue, classe=classe, periode=periode,
                            note=val_s1 if session_mode != 'rattrapage' else None,
                            note_rattrapage=val_ratt,
                            saisi_par=request.user,
                        )
                    nb_importees += 1

        # ── IMPORT SCOLAIRE ──────────────────────────────────────────────────
        else:
            matiere = get_object_or_404(Matiere, pk=matiere_id, etablissement=etab)
            if not _verifier_acces_enseignant_matiere(request.user, etab, annee, classe, matiere):
                messages.error(request, "Vous n'êtes pas affecté à cette matière dans cette classe.")
                return redirect(redirect_url)

            is_premier_cycle = bool(cycle and cycle.is_premier_cycle and cycle.utilise_compositions_multiples)
            mode_calcul = cycle.mode_calcul if cycle else 'classique'
            periode = None
            if not is_premier_cycle or matiere.is_conduite:
                periode = get_object_or_404(Periode, pk=periode_id, etablissement=etab)
                if not periode.peut_saisir and not request.user.is_admin:
                    messages.error(request, "La saisie est clôturée pour cette période.")
                    return redirect(redirect_url)

            for r_idx, row in enumerate(ws.iter_rows(min_row=5, values_only=True), 5):
                if not row or not row[0]:
                    continue
                mat = str(row[0]).strip().upper()
                eleve = eleves_par_matricule.get(mat)
                if not eleve:
                    continue

                c_val1 = row[2] if len(row) > 2 else None
                c_val2 = row[3] if len(row) > 3 else None

                try:
                    if matiere.is_conduite:
                        nc = _parse_dec(c_val1, 0, 18)
                        if nc is None:
                            continue
                        NotePeriode.objects.update_or_create(
                            eleve=eleve, matiere=matiere, classe=classe, periode=periode,
                            defaults={'note_conduite': nc, 'saisi_par': request.user}
                        )
                        nb_importees += 1

                    elif is_premier_cycle:
                        num_int = int(numero) if (numero and str(numero).isdigit()) else 1
                        note_10 = _parse_dec(c_val1, 0, 10)
                        if note_10 is None:
                            continue
                        Composition.objects.update_or_create(
                            eleve=eleve, matiere=matiere, classe=classe, annee=annee, numero=num_int,
                            defaults={'note': note_10, 'note_max': Decimal('10'), 'saisi_par': request.user}
                        )
                        nb_importees += 1

                    elif mode_calcul == 'direct':
                        nd = _parse_dec(c_val1, 0, 20)
                        if nd is None:
                            continue
                        NotePeriode.objects.update_or_create(
                            eleve=eleve, matiere=matiere, classe=classe, periode=periode,
                            defaults={
                                'moy_classe': nd, 'moy_compo': nd * 2,
                                'note_max_classe': Decimal('20'), 'note_max_compo': Decimal('40'),
                                'saisi_par': request.user,
                            }
                        )
                        nb_importees += 1

                    else:
                        mc = _parse_dec(c_val1, 0, 20)
                        mcompo = _parse_dec(c_val2, 0, 40)
                        if mc is None and mcompo is None:
                            continue
                        exist = NotePeriode.objects.filter(
                            eleve=eleve, matiere=matiere, classe=classe, periode=periode
                        ).first()
                        if exist:
                            avant_mc = exist.moy_classe
                            avant_cp = exist.moy_compo
                            if mc is not None:
                                exist.moy_classe = mc
                            if mcompo is not None:
                                exist.moy_compo = mcompo
                            exist.modifie_par = request.user
                            exist.save()
                            if avant_mc is not None and mc is not None and avant_mc != mc:
                                LogModificationNote.objects.create(
                                    note_periode=exist, modifie_par=request.user,
                                    role_modifiant=request.user.role, champ_modifie='moy_classe (Import Excel)',
                                    valeur_avant=str(avant_mc), valeur_apres=str(mc), notif_envoyee=True
                                )
                            if avant_cp is not None and mcompo is not None and avant_cp != mcompo:
                                LogModificationNote.objects.create(
                                    note_periode=exist, modifie_par=request.user,
                                    role_modifiant=request.user.role, champ_modifie='moy_compo (Import Excel)',
                                    valeur_avant=str(avant_cp), valeur_apres=str(mcompo), notif_envoyee=True
                                )
                        else:
                            NotePeriode.objects.create(
                                eleve=eleve, matiere=matiere, classe=classe, periode=periode,
                                moy_classe=mc, moy_compo=mcompo,
                                note_max_classe=Decimal('20'), note_max_compo=Decimal('40'),
                                saisi_par=request.user,
                            )
                        nb_importees += 1
                except (ValueError, InvalidOperation) as e:
                    erreurs.append(f"Ligne {r_idx} ({mat}) : {e}")

    if nb_importees:
        messages.success(request, f"Import Excel réussi : {nb_importees} note(s) enregistrée(s).")
    else:
        messages.warning(request, "Aucune note n'a été importée (vérifiez que les colonnes de notes sont remplies).")
    for err in erreurs[:5]:
        messages.warning(request, err)

    return redirect(redirect_url)

