"""
Service de generation Excel (.xlsx) et CSV pour l'exportation des notes.
Separe de notes/views_export.py pour isoler le formatage et la logique metier HTTP.
"""
import csv
import re
from django.http import HttpResponse
from django.utils import timezone
from core.validators import safe_excel_value

def _appreciation_sur_20(val):
    if val is None:
        return "Non saisi"
    v = float(val)
    if v >= 16:
        return "Très Bien"
    if v >= 14:
        return "Bien"
    if v >= 12:
        return "Assez Bien"
    if v >= 10:
        return "Passable"
    if v >= 8:
        return "Insuffisant"
    return "Très Insuffisant"


def _appreciation_sur_10(val):
    if val is None:
        return "Non saisi"
    v = float(val)
    if v >= 8:
        return "Très Bien"
    if v >= 7:
        return "Bien"
    if v >= 6:
        return "Assez Bien"
    if v >= 5:
        return "Passable"
    return "Insuffisant"


def _clean_sheet_title(title, existing_titles):
    """Nettoie un nom d'onglet Excel (max 31 caractères, sans caractères interdits)."""
    cleaned = re.sub(r'[\[\]\:\*\?\/\\]', '-', str(title or 'Feuille')).strip()
    if not cleaned:
        cleaned = "Matiere"
    base = cleaned[:28]
    candidate = base
    idx = 2
    while candidate.lower() in existing_titles:
        candidate = f"{base[:25]}_{idx}"
        idx += 1
    existing_titles.add(candidate.lower())
    return candidate


def _get_entete_officiel(etab, modele, is_universite):
    """Construit les lignes d'en-tête institutionnel (Gauche : Ministère/Étab, Droite : République/Devise)."""
    if is_universite:
        def_g1 = "MINISTÈRE DE L'ENSEIGNEMENT SUPÉRIEUR"
        def_g2 = "ET DE LA RECHERCHE SCIENTIFIQUE"
    else:
        def_g1 = "MINISTÈRE DE L'ÉDUCATION NATIONALE"
        def_g2 = "ACADÉMIE D'ENSEIGNEMENT"

    g1 = (modele.ligne1_gauche if (modele and modele.ligne1_gauche) else def_g1)
    g2 = (modele.ligne2_gauche if (modele and modele.ligne2_gauche) else def_g2)
    g3 = (modele.ligne3_gauche if (modele and modele.ligne3_gauche) else etab.nom)

    d1 = (modele.ligne1_droite if (modele and modele.ligne1_droite) else "RÉPUBLIQUE DU MALI")
    d2 = (modele.ligne2_droite if (modele and modele.ligne2_droite) else "Un Peuple — Un But — Une Foi")
    d3 = (modele.ligne3_droite if (modele and modele.ligne3_droite) else "")

    coords = []
    if etab.adresse:
        coords.append(etab.adresse)
    if etab.telephone:
        coords.append(f"Tél : {etab.telephone}")
    if etab.email:
        coords.append(etab.email)

    return {
        'gauche_1': g1,
        'gauche_2': g2,
        'gauche_3': g3,
        'droite_1': d1,
        'droite_2': d2,
        'droite_3': d3,
        'nom_etab': (modele.nom_etablissement_custom if (modele and modele.nom_etablissement_custom) else etab.nom),
        'slogan': etab.slogan or '',
        'coordonnees': "  •  ".join(coords),
        'sign_gauche': (modele.label_signature_gauche if (modele and modele.label_signature_gauche) else "L'Enseignant / Responsable"),
        'sign_droite': (modele.label_signature_droite if (modele and modele.label_signature_droite) else ("Le Doyen / Directeur" if is_universite else "Le Directeur / Proviseur")),
    }


def _get_headers_for_cycle(is_universite, is_premier_cycle):
    if is_universite:
        return [
            "N°", "Matricule", "Nom", "Prénom", "Sexe", "Classe", "Filière",
            "Semestre", "Code UE", "Intitulé de l'UE", "Crédits ECTS",
            "Session 1 (/20)", "Rattrapage (/20)", "Note Retenue (/20)",
            "Crédits Obtenus", "Décision UE", "Mention", "Enseignant / Saisi par"
        ]
    if is_premier_cycle:
        return [
            "N°", "Matricule", "Nom", "Prénom", "Sexe", "Classe",
            "Composition", "Matière", "Note (/10)", "Équivalent (/20)",
            "Statut", "Appréciation", "Saisi par"
        ]
    return [
        "N°", "Matricule", "Nom", "Prénom", "Sexe", "Classe", "Série",
        "Période", "Matière", "Coef.", "Note Classe (/20)", "Note Compo (/40)",
        "Moyenne (/20)", "Total Pondéré", "Statut", "Appréciation", "Enseignant / Saisi par"
    ]


def _row_to_values(idx, r, is_universite, is_premier_cycle):
    el = r['eleve']
    if is_universite:
        return [
            idx,
            safe_excel_value(el.matricule),
            safe_excel_value(el.nom),
            safe_excel_value(el.prenom),
            el.sexe,
            safe_excel_value(r['classe'].nom),
            safe_excel_value(r['filiere'] or '—'),
            safe_excel_value(r['semestre']),
            safe_excel_value(r['code_matiere']),
            safe_excel_value(r['nom_matiere']),
            r['coef_ou_credits'],
            r['note_1'] if r['note_1'] is not None else '',
            r['note_2'] if r['note_2'] is not None else '',
            r['note_finale'] if r['note_finale'] is not None else '',
            r['points_ou_credits_valides'],
            safe_excel_value(r['statut_label']),
            safe_excel_value(r['mention']),
            safe_excel_value(r['saisi_par']),
        ]
    if is_premier_cycle:
        return [
            idx,
            safe_excel_value(el.matricule),
            safe_excel_value(el.nom),
            safe_excel_value(el.prenom),
            el.sexe,
            safe_excel_value(r['classe'].nom),
            safe_excel_value(r['semestre']),
            safe_excel_value(r['nom_matiere']),
            r['note_1'] if r['note_1'] is not None else '',
            r['note_2'] if r['note_2'] is not None else '',
            safe_excel_value(r['statut_label']),
            safe_excel_value(r['mention']),
            safe_excel_value(r['saisi_par']),
        ]
    return [
        idx,
        safe_excel_value(el.matricule),
        safe_excel_value(el.nom),
        safe_excel_value(el.prenom),
        el.sexe,
        safe_excel_value(r['classe'].nom),
        safe_excel_value(r['filiere'] or '—'),
        safe_excel_value(r['semestre']),
        safe_excel_value(r['nom_matiere']),
        r['coef_ou_credits'],
        r['note_1'] if r['note_1'] is not None else '',
        r['note_2'] if r['note_2'] is not None else '',
        r['note_finale'] if r['note_finale'] is not None else '',
        r['points_ou_credits_valides'] if r['points_ou_credits_valides'] is not None else '',
        safe_excel_value(r['statut_label']),
        safe_excel_value(r['mention']),
        safe_excel_value(r['saisi_par']),
    ]


def _ecrire_entete_institutionnel_excel(ws, nb_cols, etab, annee, entete, fiche_meta, matiere_override, rows_list, is_universite, is_premier_cycle):
    """
    Dessine un véritable en-tête officiel de fiche sur les lignes 1 à 8 d'une feuille Excel :
    - Lignes 1 à 3 : Bloc Gauche (Ministère / Académie / Établissement) & Bloc Droite (République du Mali / Devise / Année)
    - Ligne 4      : Bandeau Titre Officiel de la Fiche
    - Lignes 5 à 7 : Cartouche d'identification structuré (Classe, Filière/Série, Matière/UE, Période, Enseignant, Effectif, Moyenne, Taux)
    Retourne le numéro de ligne où commence le tableau des notes (ligne 9).
    """
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    last_col_letter = get_column_letter(nb_cols)
    mid_col = max(4, nb_cols // 2)
    mid_left_letter = get_column_letter(mid_col)
    mid_right_letter = get_column_letter(mid_col + 1)

    navy_fill = PatternFill(start_color="0F2942", end_color="0F2942", fill_type="solid")
    cartouche_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    label_fill = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")

    font_inst_bold = Font(name="Arial", bold=True, size=10, color="0F2942")
    font_inst_sub = Font(name="Arial", italic=True, size=9, color="334155")
    font_etab = Font(name="Arial", bold=True, size=12, color="1565C0")
    font_banner = Font(name="Arial", bold=True, size=12, color="FFFFFF")
    font_lbl = Font(name="Arial", bold=True, size=9, color="334155")
    font_val = Font(name="Arial", bold=True, size=10, color="0F172A")

    thin_side = Side(style="thin", color="CBD5E1")
    med_bottom = Side(style="medium", color="1565C0")
    box_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

    # ── Ligne 1 : Ministère (Gauche) | République du Mali (Droite) ────────────
    ws.merge_cells(f"A1:{mid_left_letter}1")
    ws["A1"] = entete['gauche_1'].upper()
    ws["A1"].font = font_inst_bold
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center")

    ws.merge_cells(f"{mid_right_letter}1:{last_col_letter}1")
    ws[f"{mid_right_letter}1"] = entete['droite_1'].upper()
    ws[f"{mid_right_letter}1"].font = font_inst_bold
    ws[f"{mid_right_letter}1"].alignment = Alignment(horizontal="right", vertical="center")
    ws.row_dimensions[1].height = 18

    # ── Ligne 2 : Académie / Sous-tutelle (Gauche) | Devise (Droite) ──────────
    ws.merge_cells(f"A2:{mid_left_letter}2")
    ws["A2"] = entete['gauche_2']
    ws["A2"].font = font_inst_sub
    ws["A2"].alignment = Alignment(horizontal="left", vertical="center")

    ws.merge_cells(f"{mid_right_letter}2:{last_col_letter}2")
    ws[f"{mid_right_letter}2"] = entete['droite_2']
    ws[f"{mid_right_letter}2"].font = font_inst_sub
    ws[f"{mid_right_letter}2"].alignment = Alignment(horizontal="right", vertical="center")
    ws.row_dimensions[2].height = 16

    # ── Ligne 3 : Nom de l'Établissement + Coordonnées | Année scolaire ───────
    ws.merge_cells(f"A3:{mid_left_letter}3")
    coord_txt = f" — {entete['coordonnees']}" if entete['coordonnees'] else ""
    ws["A3"] = f"{entete['nom_etab'].upper()}{coord_txt}"
    ws["A3"].font = font_etab
    ws["A3"].alignment = Alignment(horizontal="left", vertical="center")

    ws.merge_cells(f"{mid_right_letter}3:{last_col_letter}3")
    annee_lbl = annee.libelle if annee else "—"
    ws[f"{mid_right_letter}3"] = f"ANNÉE {'UNIVERSITAIRE' if is_universite else 'SCOLAIRE'} : {annee_lbl}"
    ws[f"{mid_right_letter}3"].font = font_etab
    ws[f"{mid_right_letter}3"].alignment = Alignment(horizontal="right", vertical="center")
    ws.row_dimensions[3].height = 22
    for c_i in range(1, nb_cols + 1):
        ws.cell(row=3, column=c_i).border = Border(bottom=med_bottom)

    # ── Ligne 4 : Bandeau Titre Officiel de la Fiche ──────────────────────────
    ws.merge_cells(f"A4:{last_col_letter}4")
    ws["A4"] = fiche_meta['titre_fiche']
    ws["A4"].fill = navy_fill
    ws["A4"].font = font_banner
    ws["A4"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[4].height = 26

    # ── Calcul des statistiques propres à cette feuille ───────────────────────
    vals_num = [r['note_finale'] for r in rows_list if r['note_finale'] is not None]
    nb_s = len(vals_num)
    nb_ok = sum(1 for r in rows_list if r['statut_code'] == 'admis')
    nb_ko = sum(1 for r in rows_list if r['statut_code'] == 'ajourne')
    moy_s = round(sum(vals_num) / nb_s, 2) if nb_s else None
    min_s = round(min(vals_num), 2) if nb_s else None
    max_s = round(max(vals_num), 2) if nb_s else None
    taux_s = round((nb_ok / nb_s) * 100, 1) if nb_s else 0.0
    echelle = 10 if is_premier_cycle else 20

    mat_txt = matiere_override or fiche_meta['matiere_label']

    # ── Lignes 5, 6, 7 : Cartouche structuré de la Fiche ──────────────────────
    cartouche_rows = [
        (
            "CLASSE / NIVEAU :", fiche_meta['classe_label'],
            "MATIÈRE / UE :", mat_txt,
            "PÉRIODE / SEMESTRE :", fiche_meta['periode_label'],
        ),
        (
            "FILIÈRE / SÉRIE :", fiche_meta['filiere_label'],
            "ENSEIGNANT :", fiche_meta['enseignant_label'],
            "FILTRE APPLIQUÉ :", fiche_meta['statut_filtre_label'],
        ),
        (
            "ÉVALUATIONS :", f"{len(rows_list)} ({nb_s} saisies)",
            "MOYENNE & EXTRÊMES :", (f"{moy_s}/{echelle}  (Min: {min_s} | Max: {max_s})" if moy_s is not None else "—"),
            "TAUX DE RÉUSSITE :", f"{nb_ok} Admis / {nb_ko} Ajournés ({taux_s}%)",
        ),
    ]

    # Répartition en 3 blocs horizontaux sur la largeur totale du tableau
    b1_lbl, b1_val_end = 1, max(3, nb_cols // 3)
    b2_lbl, b2_val_end = b1_val_end + 1, max(b1_val_end + 3, (nb_cols * 2) // 3)
    b3_lbl, b3_val_end = b2_val_end + 1, nb_cols

    for idx_r, (l1, v1, l2, v2, l3, v3) in enumerate(cartouche_rows, start=5):
        ws.row_dimensions[idx_r].height = 20
        for c_i in range(1, nb_cols + 1):
            cell = ws.cell(row=idx_r, column=c_i)
            cell.fill = cartouche_fill
            cell.border = box_border

        # Bloc 1
        ws.cell(row=idx_r, column=b1_lbl, value=l1).font = font_lbl
        ws.cell(row=idx_r, column=b1_lbl).fill = label_fill
        ws.merge_cells(start_row=idx_r, start_column=b1_lbl + 1, end_row=idx_r, end_column=b1_val_end)
        c_v1 = ws.cell(row=idx_r, column=b1_lbl + 1, value=v1)
        c_v1.font = font_val
        c_v1.alignment = Alignment(horizontal="left", vertical="center")

        # Bloc 2
        ws.cell(row=idx_r, column=b2_lbl, value=l2).font = font_lbl
        ws.cell(row=idx_r, column=b2_lbl).fill = label_fill
        ws.merge_cells(start_row=idx_r, start_column=b2_lbl + 1, end_row=idx_r, end_column=b2_val_end)
        c_v2 = ws.cell(row=idx_r, column=b2_lbl + 1, value=v2)
        c_v2.font = font_val
        c_v2.alignment = Alignment(horizontal="left", vertical="center")

        # Bloc 3
        ws.cell(row=idx_r, column=b3_lbl, value=l3).font = font_lbl
        ws.cell(row=idx_r, column=b3_lbl).fill = label_fill
        ws.merge_cells(start_row=idx_r, start_column=b3_lbl + 1, end_row=idx_r, end_column=b3_val_end)
        c_v3 = ws.cell(row=idx_r, column=b3_lbl + 1, value=v3)
        c_v3.font = font_val
        c_v3.alignment = Alignment(horizontal="left", vertical="center")

    ws.row_dimensions[8].height = 8  # Ligne d'espacement avant le tableau
    return 9, nb_s, nb_ok, moy_s, taux_s


def _remplir_feuille_detail(ws, etab, annee, entete, fiche_meta, matiere_override, rows_list, is_universite, is_premier_cycle):
    """Remplit une feuille openpyxl avec En-tête officiel, Cartouche, AutoFilter et couleurs conditionnelles."""
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    headers = _get_headers_for_cycle(is_universite, is_premier_cycle)
    nb_cols = len(headers)
    last_col_letter = get_column_letter(nb_cols)

    header_row, nb_s, nb_ok, moy_s, taux_s = _ecrire_entete_institutionnel_excel(
        ws, nb_cols, etab, annee, entete, fiche_meta, matiere_override, rows_list, is_universite, is_premier_cycle
    )

    sub_fill = PatternFill(start_color="1565C0", end_color="1565C0", fill_type="solid")
    kpi_fill = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")
    zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    green_fill = PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid")
    red_fill = PatternFill(start_color="FFEBEE", end_color="FFEBEE", fill_type="solid")
    warn_fill = PatternFill(start_color="FFF8E1", end_color="FFF8E1", fill_type="solid")

    font_header = Font(name="Arial", color="FFFFFF", bold=True, size=10)
    font_bold = Font(name="Arial", bold=True, size=10)
    font_green = Font(name="Arial", color="1B5E20", bold=True, size=10)
    font_red = Font(name="Arial", color="B71C1C", bold=True, size=10)

    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )

    # En-têtes de colonnes (avec AutoFilter natif Excel)
    ws.row_dimensions[header_row].height = 25
    for col_idx, h_text in enumerate(headers, 1):
        c = ws.cell(row=header_row, column=col_idx, value=h_text)
        c.fill = sub_fill
        c.font = font_header
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = thin_border

    note_col_idx = 14 if is_universite else (9 if is_premier_cycle else 13)
    statut_col_idx = 16 if is_universite else (11 if is_premier_cycle else 15)

    for i, r in enumerate(rows_list, 1):
        row_num = header_row + i
        ws.row_dimensions[row_num].height = 20
        values = _row_to_values(i, r, is_universite, is_premier_cycle)
        row_fill = zebra_fill if i % 2 == 0 else None
        for col_idx, val in enumerate(values, 1):
            c = ws.cell(row=row_num, column=col_idx, value=val)
            c.border = thin_border
            if row_fill:
                c.fill = row_fill
            if isinstance(val, (int, float)):
                c.alignment = Alignment(horizontal="center", vertical="center")
                if isinstance(val, float):
                    c.number_format = "0.00"
            elif col_idx in (1, 5, 8, 11):
                c.alignment = Alignment(horizontal="center", vertical="center")

        c_note = ws.cell(row=row_num, column=note_col_idx)
        c_statut = ws.cell(row=row_num, column=statut_col_idx)
        if r['statut_code'] == 'admis':
            c_note.font = font_green
            c_statut.fill = green_fill
            c_statut.font = font_green
        elif r['statut_code'] == 'ajourne':
            c_note.font = font_red
            c_statut.fill = red_fill
            c_statut.font = font_red
        else:
            c_statut.fill = warn_fill

    # Ligne de synthèse + Signatures en bas de fiche
    last_data_row = header_row + len(rows_list)
    if rows_list:
        sum_row = last_data_row + 1
        ws.row_dimensions[sum_row].height = 22
        for col_idx in range(1, nb_cols + 1):
            ws.cell(row=sum_row, column=col_idx).border = thin_border
            ws.cell(row=sum_row, column=col_idx).fill = kpi_fill
        ws.cell(row=sum_row, column=2, value="SYNTHÈSE DE LA FICHE").font = font_bold
        ws.cell(row=sum_row, column=3, value=f"Évalués : {nb_s}/{len(rows_list)}").font = font_bold
        ws.cell(row=sum_row, column=4, value=f"Admis : {nb_ok} ({taux_s}%)").font = font_bold
        if moy_s is not None:
            c_moy = ws.cell(row=sum_row, column=note_col_idx, value=moy_s)
            c_moy.font = font_bold
            c_moy.number_format = "0.00"

        # Bloc signatures officiel en bas de la feuille Excel
        sign_row = sum_row + 2
        ws.cell(row=sign_row, column=2, value=entete['sign_gauche']).font = font_bold
        ws.cell(row=sign_row, column=max(2, nb_cols - 3), value=entete['sign_droite']).font = font_bold
        ws.cell(row=sign_row + 1, column=max(2, nb_cols - 3), value=f"Fait le {timezone.now().strftime('%d/%m/%Y')}").font = Font(italic=True, size=9, color="475569")

    # Activer AutoFilter Excel sur toute la plage de données + figer les volets sous l'en-tête
    ws.auto_filter.ref = f"A{header_row}:{last_col_letter}{max(header_row, last_data_row)}"
    ws.freeze_panes = f"A{header_row + 1}"

    # Ajuster automatiquement la largeur des colonnes
    for col_idx in range(1, nb_cols + 1):
        col_letter = get_column_letter(col_idx)
        max_len = len(str(headers[col_idx - 1]))
        for r_idx in range(header_row + 1, min(last_data_row + 1, header_row + 150)):
            v = ws.cell(row=r_idx, column=col_idx).value
            if v is not None:
                max_len = max(max_len, len(str(v)))
        ws.column_dimensions[col_letter].width = min(max(max_len + 4, 11), 36)


def _generer_xlsx_detail(etab, annee, classe, periode, entete, fiche_meta, is_universite, is_premier_cycle, lignes, stats):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Fiche_Notes"

    _remplir_feuille_detail(ws, etab, annee, entete, fiche_meta, None, lignes, is_universite, is_premier_cycle)

    slug_c = re.sub(r'[^a-zA-Z0-9_-]', '_', classe.nom) if classe else "toutes_classes"
    filename = f"fiche_notes_{etab.code}_{slug_c}.xlsx"
    resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    wb.save(resp)
    return resp


def _generer_xlsx_multi_feuilles(etab, annee, classe, periode, entete, fiche_meta, is_universite, is_premier_cycle, lignes, stats):
    """Génère un classeur Excel professionnel avec 1 feuille Synthèse officielle + 1 fiche officielle par Matière/UE."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws_syn = wb.active
    ws_syn.title = "Synthese_Deliberation"
    existing_titles = {"synthese_deliberation"}

    # ── 1. Construire la synthèse par élève ───────────────────────────────────
    par_eleve = {}
    matieres_codes = []
    for r in lignes:
        el = r['eleve']
        code_m = r['code_matiere']
        if code_m not in matieres_codes:
            matieres_codes.append(code_m)
        if el.pk not in par_eleve:
            par_eleve[el.pk] = {
                'eleve': el,
                'classe': r['classe'],
                'notes_par_mat': {},
                'total_pts': 0.0,
                'total_coef': 0,
                'credits_valides': 0,
                'credits_requis': 0,
            }
        entry = par_eleve[el.pk]
        entry['notes_par_mat'][code_m] = r['note_finale']
        if r['note_finale'] is not None:
            c_val = r['coef_ou_credits'] or 1
            entry['total_pts'] += float(r['note_finale']) * c_val
            entry['total_coef'] += c_val
        if is_universite:
            entry['credits_requis'] += (r['coef_ou_credits'] or 0)
            if r['valide']:
                entry['credits_valides'] += (r['coef_ou_credits'] or 0)

    synthese_list = []
    for pk, item in par_eleve.items():
        moy = round(item['total_pts'] / item['total_coef'], 2) if item['total_coef'] > 0 else None
        item['moyenne'] = moy
        synthese_list.append(item)

    synthese_list.sort(
        key=lambda x: (x['moyenne'] is not None, x['moyenne'] if x['moyenne'] is not None else -1),
        reverse=True,
    )
    for idx, item in enumerate(synthese_list, 1):
        item['rang'] = idx if item['moyenne'] is not None else None

    syn_headers = ["Rang", "Matricule", "Nom", "Prénom", "Sexe", "Classe"] + matieres_codes
    if is_universite:
        syn_headers += ["Crédits Validés", "Moyenne Générale (/20)", "Décision Jury", "Mention"]
    elif is_premier_cycle:
        syn_headers += ["Moyenne Générale (/10)", "Décision", "Appréciation"]
    else:
        syn_headers += ["Total Pondéré", "Total Coef", "Moyenne Générale (/20)", "Décision", "Appréciation"]

    nb_cols = len(syn_headers)
    last_col = get_column_letter(nb_cols)

    meta_syn = dict(fiche_meta)
    meta_syn['titre_fiche'] = "PROCÈS-VERBAL DE SYNTHÈSE & CLASSEMENT GÉNÉRAL"
    header_row, _, _, _, _ = _ecrire_entete_institutionnel_excel(
        ws_syn, nb_cols, etab, annee, entete, meta_syn, "Synthèse Toutes Matières / UEs", lignes, is_universite, is_premier_cycle
    )

    sub_fill = PatternFill(start_color="1565C0", end_color="1565C0", fill_type="solid")
    green_fill = PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid")
    red_fill = PatternFill(start_color="FFEBEE", end_color="FFEBEE", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )

    ws_syn.row_dimensions[header_row].height = 25
    for col_idx, h_text in enumerate(syn_headers, 1):
        c = ws_syn.cell(row=header_row, column=col_idx, value=h_text)
        c.fill = sub_fill
        c.font = Font(name="Arial", color="FFFFFF", bold=True, size=10)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = thin_border

    seuil = 5.0 if is_premier_cycle else 10.0
    for i, item in enumerate(synthese_list, 1):
        r_num = header_row + i
        ws_syn.row_dimensions[r_num].height = 20
        el = item['eleve']
        moy = item['moyenne']
        admis = bool(moy is not None and moy >= seuil)
        decision = "Non évalué" if moy is None else ("Admis / Validé" if admis else "Ajourné")
        appr = _appreciation_sur_10(moy) if is_premier_cycle else _appreciation_sur_20(moy)

        row_vals = [
            item['rang'] or '—',
            safe_excel_value(el.matricule),
            safe_excel_value(el.nom),
            safe_excel_value(el.prenom),
            el.sexe,
            safe_excel_value(item['classe'].nom),
        ]
        for code_m in matieres_codes:
            v_m = item['notes_par_mat'].get(code_m)
            row_vals.append(v_m if v_m is not None else '')

        if is_universite:
            row_vals += [
                f"{item['credits_valides']}/{item['credits_requis']}",
                moy if moy is not None else '',
                decision,
                appr,
            ]
        elif is_premier_cycle:
            row_vals += [
                moy if moy is not None else '',
                decision,
                appr,
            ]
        else:
            row_vals += [
                round(item['total_pts'], 2) if item['total_coef'] else '',
                item['total_coef'] or '',
                moy if moy is not None else '',
                decision,
                appr,
            ]

        for col_idx, val in enumerate(row_vals, 1):
            c = ws_syn.cell(row=r_num, column=col_idx, value=val)
            c.border = thin_border
            if isinstance(val, (int, float)):
                c.alignment = Alignment(horizontal="center", vertical="center")
                if isinstance(val, float):
                    c.number_format = "0.00"
        if moy is not None:
            dec_cell = ws_syn.cell(row=r_num, column=nb_cols - 1)
            dec_cell.fill = green_fill if admis else red_fill
            dec_cell.font = Font(name="Arial", color="1B5E20" if admis else "B71C1C", bold=True, size=10)

    last_syn_row = header_row + len(synthese_list)
    ws_syn.auto_filter.ref = f"A{header_row}:{last_col}{max(header_row, last_syn_row)}"
    ws_syn.freeze_panes = f"G{header_row + 1}"
    for col_idx in range(1, nb_cols + 1):
        col_letter = get_column_letter(col_idx)
        ws_syn.column_dimensions[col_letter].width = 15 if col_idx > 6 else 14

    # ── 2. Créer 1 fiche officielle dédiée par Matière / UE ───────────────────
    par_matiere = {}
    for r in lignes:
        key = (r['code_matiere'], r['nom_matiere'], r['coef_ou_credits'])
        par_matiere.setdefault(key, []).append(r)

    for (code_m, nom_m, coef_m), m_rows in par_matiere.items():
        sheet_name = _clean_sheet_title(f"{code_m}_{nom_m}", existing_titles)
        ws_m = wb.create_sheet(title=sheet_name)
        unit_lbl = "crédits ECTS" if is_universite else "coef."
        mat_override = f"{code_m} — {nom_m} ({coef_m} {unit_lbl})"
        _remplir_feuille_detail(ws_m, etab, annee, entete, fiche_meta, mat_override, m_rows, is_universite, is_premier_cycle)

    slug_c = re.sub(r'[^a-zA-Z0-9_-]', '_', classe.nom) if classe else "toutes_classes"
    filename = f"deliberation_multifeuilles_{etab.code}_{slug_c}.xlsx"
    resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    wb.save(resp)
    return resp


def _generer_csv_detail(etab, annee, classe, periode, entete, fiche_meta, is_universite, is_premier_cycle, lignes, stats):
    slug_c = re.sub(r'[^a-zA-Z0-9_-]', '_', classe.nom) if classe else "toutes_classes"
    filename = f"fiche_notes_{etab.code}_{slug_c}.csv"
    resp = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(resp, delimiter=';')
    # En-tête officiel de la fiche en haut du CSV
    writer.writerow([entete['gauche_1'], "", "", "", entete['droite_1']])
    writer.writerow([entete['nom_etab'], "", "", "", entete['droite_2']])
    writer.writerow([fiche_meta['titre_fiche'], f"Année : {annee.libelle if annee else ''}"])
    writer.writerow([
        f"Classe : {fiche_meta['classe_label']}",
        f"Filière/Série : {fiche_meta['filiere_label']}",
        f"Matière/UE : {fiche_meta['matiere_label']}",
        f"Période : {fiche_meta['periode_label']}",
        f"Moyenne : {stats['moy_globale'] or '—'}/{stats['echelle']}",
        f"Taux réussite : {stats['taux_reussite']}%",
    ])
    writer.writerow([])
    headers = _get_headers_for_cycle(is_universite, is_premier_cycle)
    writer.writerow(headers)
    for i, r in enumerate(lignes, 1):
        writer.writerow(_row_to_values(i, r, is_universite, is_premier_cycle))
    return resp
