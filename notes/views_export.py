"""
Centre d'Exportation & Filtrage Avancé des Notes — SmartSchool V3
=================================================================
Supporte les 3 architectures pédagogiques :
- Université (LMD) : NoteUE (/20, Rattrapage, Crédits ECTS, Mention)
- Secondaire & Lycée : NotePeriode (Note Classe, Note Compo, Moyenne /20, Coef)
- 1er Cycle Fondamental : Composition (/10, Équivalent /20)

Formats d'export professionnels avec En-tête Institutionnel Officiel :
- xlsx_detail : Fiche Excel détaillée par Matière / UE avec En-tête officiel + Cartouche + AutoFilter
- xlsx_multi  : Classeur Excel Multi-Feuilles (1 feuille Synthèse + 1 fiche officielle par Matière/UE)
- csv         : Fichier CSV (UTF-8 avec BOM pour Excel français, séparateur ';')
"""
import csv
import re
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils import timezone

from accounts.permissions import permission_required, is_etab_superieur
from core.cycle_filter import get_classes_actives
from core.validators import safe_excel_value
from etablissements.models import Classe, AnneeScolaire, UEUniversite, ModeleDocument, AffectationMatiere
from notes.models import Matiere, Periode, NotePeriode, NoteUE, Composition
from notes.services import get_matieres_pour_classe, get_coefficients_map
from notes.views_universite import _filtrer_ues_filiere


from notes.services_export import (
    _appreciation_sur_20,
    _appreciation_sur_10,
    _get_entete_officiel,
    _generer_xlsx_detail,
    _generer_xlsx_multi_feuilles,
    _generer_csv_detail,
)

@login_required
@permission_required('notes')
def export_notes_view(request):
    etab = getattr(request, 'etablissement', None)
    if not etab:
        return redirect('dashboard')

    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
    modele = (
        ModeleDocument.objects.filter(etablissement=etab, type_document='bulletin', is_actif=True).first()
        or ModeleDocument.objects.filter(etablissement=etab, is_actif=True).first()
    )

    classes = (
        get_classes_actives(etab, annee, user=request.user)
        .select_related('niveau', 'niveau__cycle', 'serie', 'professeur_principal')
        .order_by('niveau__cycle__ordre', 'niveau__ordre', 'nom')
        if annee else Classe.objects.none()
    )

    # Filtrage enseignant : limiter aux classes qui lui sont affectées
    if request.user.is_enseignant and annee:
        from notes.models import EmploiDuTemps
        aff_c = set(AffectationMatiere.objects.filter(
            enseignant__user=request.user, annee=annee
        ).values_list('classe_id', flat=True))
        edt_c = set(EmploiDuTemps.objects.filter(
            enseignant=request.user, classe__etablissement=etab, classe__annee=annee
        ).values_list('classe_id', flat=True))
        ue_c = set(NoteUE.objects.filter(
            saisi_par=request.user, periode__annee=annee
        ).values_list('classe_id', flat=True))
        allowed_c = aff_c | edt_c | ue_c
        classes = classes.filter(pk__in=allowed_c)

    # ── Paramètres de filtrage ────────────────────────────────────────────────
    classe_id = request.GET.get('classe', '').strip()
    periode_id = request.GET.get('periode', '').strip()
    numero_str = request.GET.get('numero', '1').strip()
    matiere_id = request.GET.get('matiere', '').strip()
    ue_id = request.GET.get('ue', '').strip()
    semestre_str = request.GET.get('semestre', '').strip()
    statut = request.GET.get('statut', '').strip()
    sexe = request.GET.get('sexe', '').strip()
    seuil_min_str = request.GET.get('seuil_min', '').strip()
    seuil_max_str = request.GET.get('seuil_max', '').strip()
    q = request.GET.get('q', '').strip()
    tri = request.GET.get('tri', 'nom').strip()
    export_format = request.GET.get('format', '').strip()

    classe = classes.filter(pk=classe_id).first() if classe_id.isdigit() else None
    if classe:
        TargetClasses = [classe]
    elif classe_id:
        # Classe demandée introuvable (ou d'un autre établissement) : aucune donnée
        TargetClasses = []
    else:
        TargetClasses = list(classes)

    # Déterminer le type de cycle dominant
    cycle = None
    if classe and classe.niveau and classe.niveau.cycle:
        cycle = classe.niveau.cycle
    elif TargetClasses:
        first_c = TargetClasses[0]
        if first_c.niveau and first_c.niveau.cycle:
            cycle = first_c.niveau.cycle

    is_universite = bool((cycle and cycle.is_universite) or is_etab_superieur(etab))
    is_premier_cycle = bool(
        cycle and cycle.is_premier_cycle and cycle.utilise_compositions_multiples and not is_universite
    )

    # Périodes / Numéros de composition
    periodes = Periode.objects.filter(etablissement=etab, annee=annee).order_by('numero') if annee else Periode.objects.none()
    periode = None
    if not is_premier_cycle and annee:
        if periode_id.isdigit():
            periode = periodes.filter(pk=int(periode_id)).first()
        if not periode:
            periode = periodes.filter(is_active=True).first() or periodes.first()
            if periode:
                periode_id = str(periode.pk)

    nb_compositions = cycle.nb_compositions_trimestre if (cycle and is_premier_cycle) else 9
    compo_numeros = list(range(1, nb_compositions + 1))
    numero = int(numero_str) if numero_str.isdigit() else 1

    # Seuils numériques
    seuil_min = None
    seuil_max = None
    try:
        if seuil_min_str != '':
            seuil_min = float(seuil_min_str.replace(',', '.'))
    except ValueError:
        pass
    try:
        if seuil_max_str != '':
            seuil_max = float(seuil_max_str.replace(',', '.'))
    except ValueError:
        pass

    # ── Liste des Matières ou UEs disponibles pour le filtre ──────────────────
    matieres_disponibles = []
    ues_disponibles = []
    semestres_disponibles = [1, 2, 3, 4, 5, 6]
    matiere_selectionnee = None
    ue_selectionnee = None

    if is_universite:
        ues_qs = UEUniversite.objects.filter(cycle__etablissement=etab).order_by('semestre', 'code')
        if classe:
            ues_qs = _filtrer_ues_filiere(ues_qs, classe)
            if classe.niveau and classe.niveau.ordre:
                n_ord = classe.niveau.ordre
                semestres_disponibles = [n_ord * 2 - 1, n_ord * 2]
        if semestre_str.isdigit():
            ues_qs = ues_qs.filter(semestre=int(semestre_str))
        ues_disponibles = list(ues_qs)
        if ue_id.isdigit():
            ue_selectionnee = UEUniversite.objects.filter(pk=int(ue_id), cycle__etablissement=etab).first()
    else:
        if classe:
            matieres_disponibles = list(get_matieres_pour_classe(classe, periode))
        else:
            matieres_disponibles = list(Matiere.objects.filter(etablissement=etab).order_by('nom'))
        if matiere_id.isdigit():
            matiere_selectionnee = Matiere.objects.filter(pk=int(matiere_id), etablissement=etab).first()

    # ── Construction des lignes détaillées (élève × matière/UE) ───────────────
    lignes_brutes = []
    echelle_max = 10.0 if is_premier_cycle else 20.0

    for c_obj in TargetClasses:
        inscriptions = list(
            c_obj.inscriptions.filter(is_active=True)
            .select_related('eleve')
            .order_by('eleve__nom', 'eleve__prenom')
        )
        if not inscriptions:
            continue

        c_cycle = c_obj.niveau.cycle if (c_obj.niveau and c_obj.niveau.cycle) else cycle
        c_is_univ = bool(c_cycle and c_cycle.is_universite)
        c_is_1er = bool(c_cycle and c_cycle.is_premier_cycle and c_cycle.utilise_compositions_multiples and not c_is_univ)

        if c_is_univ:
            c_ues = UEUniversite.objects.filter(cycle=c_cycle).order_by('semestre', 'code')
            c_ues = _filtrer_ues_filiere(c_ues, c_obj)
            if c_obj.niveau and c_obj.niveau.ordre:
                n_ord = c_obj.niveau.ordre
                c_ues = c_ues.filter(semestre__in=[n_ord * 2 - 1, n_ord * 2])
            if semestre_str.isdigit():
                c_ues = c_ues.filter(semestre=int(semestre_str))
            elif periode and periode.numero in (1, 2) and c_obj.niveau and c_obj.niveau.ordre:
                sem_auto = (c_obj.niveau.ordre - 1) * 2 + periode.numero
                c_ues_sem = c_ues.filter(semestre=sem_auto)
                if c_ues_sem.exists():
                    c_ues = c_ues_sem
            if ue_id.isdigit():
                c_ues = c_ues.filter(pk=int(ue_id))
            c_ues_list = list(c_ues)

            notes_qs = NoteUE.objects.filter(classe=c_obj, ue__in=c_ues_list).select_related('saisi_par')
            if periode:
                notes_qs = notes_qs.filter(periode=periode)
            notes_map = {(n.eleve_id, n.ue_id): n for n in notes_qs}

            for insc in inscriptions:
                el = insc.eleve
                for ue_obj in c_ues_list:
                    n_obj = notes_map.get((el.pk, ue_obj.pk))
                    note_s1 = float(n_obj.note) if (n_obj and n_obj.note is not None) else None
                    note_ratt = float(n_obj.note_rattrapage) if (n_obj and n_obj.note_rattrapage is not None) else None
                    note_finale = float(n_obj.note_retenue) if (n_obj and n_obj.note_retenue is not None) else None
                    valide = bool(n_obj.credits_valides) if (n_obj and note_finale is not None) else False
                    has_ratt = note_ratt is not None
                    if note_finale is None:
                        statut_code = 'manquant'
                        statut_label = 'Non saisi'
                    elif valide:
                        statut_code = 'admis'
                        statut_label = 'Validé (Ratt.)' if has_ratt and (note_s1 is None or note_s1 < 10) else 'Validé'
                    else:
                        statut_code = 'ajourne'
                        statut_label = 'Ajourné'

                    lignes_brutes.append({
                        'type_ligne': 'universite',
                        'eleve': el,
                        'classe': c_obj,
                        'filiere': c_obj.filiere or (c_obj.nom.split(' ', 1)[1] if ' ' in c_obj.nom else ''),
                        'code_matiere': ue_obj.code,
                        'nom_matiere': ue_obj.nom,
                        'matiere_label': f"{ue_obj.code} — {ue_obj.nom}",
                        'semestre': f"S{ue_obj.semestre}",
                        'coef_ou_credits': ue_obj.credits,
                        'note_1': note_s1,
                        'note_2': note_ratt,
                        'note_finale': note_finale,
                        'points_ou_credits_valides': ue_obj.credits if valide else 0,
                        'valide': valide,
                        'has_rattrapage': has_ratt,
                        'statut_code': statut_code,
                        'statut_label': statut_label,
                        'mention': (n_obj.mention if (n_obj and n_obj.mention) else _appreciation_sur_20(note_finale)),
                        'saisi_par': ((n_obj.saisi_par.get_full_name() or n_obj.saisi_par.username) if (n_obj and n_obj.saisi_par) else '—'),
                        'periode_pk': periode.pk if periode else None,
                    })

        elif c_is_1er:
            c_mats = list(get_matieres_pour_classe(c_obj))
            if matiere_id.isdigit():
                c_mats = [m for m in c_mats if m.pk == int(matiere_id)]
            compos_qs = Composition.objects.filter(
                classe=c_obj, annee=annee, numero=numero, matiere__in=c_mats
            ).select_related('saisi_par')
            compos_map = {(cp.eleve_id, cp.matiere_id): cp for cp in compos_qs}

            for insc in inscriptions:
                el = insc.eleve
                for m_obj in c_mats:
                    cp_obj = compos_map.get((el.pk, m_obj.pk))
                    n_max = float(cp_obj.note_max) if (cp_obj and cp_obj.note_max and cp_obj.note_max > 0) else 10.0
                    note_10 = round((float(cp_obj.note) / n_max) * 10.0, 2) if (cp_obj and cp_obj.note is not None) else None
                    note_20 = round(note_10 * 2, 2) if note_10 is not None else None
                    valide = bool(note_10 is not None and note_10 >= 5.0)
                    if note_10 is None:
                        statut_code = 'manquant'
                        statut_label = 'Non saisi'
                    elif valide:
                        statut_code = 'admis'
                        statut_label = 'Validé (≥5/10)'
                    else:
                        statut_code = 'ajourne'
                        statut_label = 'Insuffisant (<5/10)'

                    lignes_brutes.append({
                        'type_ligne': 'premier_cycle',
                        'eleve': el,
                        'classe': c_obj,
                        'filiere': '',
                        'code_matiere': m_obj.code or m_obj.nom[:4].upper(),
                        'nom_matiere': m_obj.nom,
                        'matiere_label': m_obj.nom,
                        'semestre': f"Compo {numero}",
                        'coef_ou_credits': 1,
                        'note_1': note_10,
                        'note_2': note_20,
                        'note_finale': note_10,
                        'points_ou_credits_valides': note_10 if note_10 is not None else 0,
                        'valide': valide,
                        'has_rattrapage': bool(note_10 is not None and 4.0 <= note_10 < 5.0),
                        'statut_code': statut_code,
                        'statut_label': statut_label,
                        'mention': _appreciation_sur_10(note_10),
                        'saisi_par': ((cp_obj.saisi_par.get_full_name() or cp_obj.saisi_par.username) if (cp_obj and cp_obj.saisi_par) else '—'),
                        'periode_pk': None,
                    })

        else:
            c_mats = list(get_matieres_pour_classe(c_obj, periode))
            if matiere_id.isdigit():
                c_mats = [m for m in c_mats if m.pk == int(matiere_id)]
            coefs_map = get_coefficients_map(c_obj, c_mats)
            notes_qs = NotePeriode.objects.filter(
                classe=c_obj, matiere__in=c_mats
            ).select_related('saisi_par', 'matiere')
            if periode:
                notes_qs = notes_qs.filter(periode=periode)
            notes_map = {(n.eleve_id, n.matiere_id): n for n in notes_qs}

            for insc in inscriptions:
                el = insc.eleve
                for m_obj in c_mats:
                    n_obj = notes_map.get((el.pk, m_obj.pk))
                    coef = coefs_map.get(m_obj.pk, m_obj.coefficient)
                    if n_obj:
                        n_obj._coef_cache = coef
                    if m_obj.is_conduite:
                        note_cl = float(n_obj.note_conduite) if (n_obj and n_obj.note_conduite is not None) else None
                        note_cp = None
                    else:
                        note_cl = float(n_obj.moy_classe) if (n_obj and n_obj.moy_classe is not None) else None
                        note_cp = float(n_obj.moy_compo) if (n_obj and n_obj.moy_compo is not None) else None
                    moy_f = float(n_obj.moyenne_finale) if (n_obj and n_obj.moyenne_finale is not None) else None
                    pts_pond = round(moy_f * coef, 2) if moy_f is not None else None
                    valide = bool(moy_f is not None and moy_f >= 10.0)
                    if moy_f is None:
                        statut_code = 'manquant'
                        statut_label = 'Non saisi'
                    elif valide:
                        statut_code = 'admis'
                        statut_label = 'Admis (≥10)'
                    else:
                        statut_code = 'ajourne'
                        statut_label = 'Insuffisant (<10)'

                    lignes_brutes.append({
                        'type_ligne': 'secondaire',
                        'eleve': el,
                        'classe': c_obj,
                        'filiere': c_obj.serie.code if c_obj.serie else '',
                        'code_matiere': m_obj.code or m_obj.nom[:4].upper(),
                        'nom_matiere': m_obj.nom,
                        'matiere_label': m_obj.nom,
                        'semestre': periode.libelle if periode else '—',
                        'coef_ou_credits': coef,
                        'note_1': note_cl,
                        'note_2': note_cp,
                        'note_finale': moy_f,
                        'points_ou_credits_valides': pts_pond,
                        'valide': valide,
                        'has_rattrapage': bool(moy_f is not None and 8.0 <= moy_f < 10.0),
                        'statut_code': statut_code,
                        'statut_label': statut_label,
                        'mention': _appreciation_sur_20(moy_f),
                        'saisi_par': ((n_obj.saisi_par.get_full_name() or n_obj.saisi_par.username) if (n_obj and n_obj.saisi_par) else '—'),
                        'periode_pk': periode.pk if periode else None,
                    })

    # ── Application des filtres utilisateur sur lignes_brutes ─────────────────
    lignes = []
    for row in lignes_brutes:
        el = row['eleve']
        nf = row['note_finale']

        if sexe in ('M', 'F') and el.sexe != sexe:
            continue

        if statut == 'admis' and row['statut_code'] != 'admis':
            continue
        elif statut == 'ajourne' and row['statut_code'] != 'ajourne':
            continue
        elif statut == 'manquant' and row['statut_code'] != 'manquant':
            continue
        elif statut == 'rattrapage' and not row['has_rattrapage']:
            continue

        if seuil_min is not None:
            if nf is None or nf < seuil_min:
                continue
        if seuil_max is not None:
            if nf is None or nf > seuil_max:
                continue

        if q:
            q_low = q.lower()
            haystack = f"{el.matricule} {el.nom} {el.prenom} {row['matiere_label']} {row['classe'].nom} {row['mention']}".lower()
            if q_low not in haystack:
                continue

        lignes.append(row)

    # ── Tri ───────────────────────────────────────────────────────────────────
    if tri == 'note_desc':
        lignes.sort(key=lambda r: (r['note_finale'] is not None, r['note_finale'] if r['note_finale'] is not None else -1), reverse=True)
    elif tri == 'note_asc':
        lignes.sort(key=lambda r: (r['note_finale'] is None, r['note_finale'] if r['note_finale'] is not None else 999))
    elif tri == 'matricule':
        lignes.sort(key=lambda r: (r['eleve'].matricule or '', r['nom_matiere']))
    elif tri == 'matiere':
        lignes.sort(key=lambda r: (r['code_matiere'], r['classe'].nom, r['eleve'].nom, r['eleve'].prenom))
    else:
        lignes.sort(key=lambda r: (r['classe'].nom, r['eleve'].nom, r['eleve'].prenom, r['code_matiere']))

    # ── Calcul des KPIs statistiques sur la sélection filtrée ─────────────────
    notes_valides_num = [r['note_finale'] for r in lignes if r['note_finale'] is not None]
    nb_total = len(lignes)
    nb_saisies = len(notes_valides_num)
    nb_manquantes = sum(1 for r in lignes if r['statut_code'] == 'manquant')
    nb_admis = sum(1 for r in lignes if r['statut_code'] == 'admis')
    nb_ajournes = sum(1 for r in lignes if r['statut_code'] == 'ajourne')
    taux_reussite = round((nb_admis / nb_saisies) * 100, 1) if nb_saisies > 0 else 0.0
    moy_globale = round(sum(notes_valides_num) / nb_saisies, 2) if nb_saisies > 0 else None
    note_max = round(max(notes_valides_num), 2) if nb_saisies > 0 else None
    note_min = round(min(notes_valides_num), 2) if nb_saisies > 0 else None

    stats = {
        'nb_total': nb_total,
        'nb_saisies': nb_saisies,
        'nb_manquantes': nb_manquantes,
        'nb_admis': nb_admis,
        'nb_ajournes': nb_ajournes,
        'taux_reussite': taux_reussite,
        'moy_globale': moy_globale,
        'note_max': note_max,
        'note_min': note_min,
        'echelle': int(echelle_max),
    }

    # ── Métadonnées de l'en-tête de la fiche (Cartouche officiel) ─────────────
    entete = _get_entete_officiel(etab, modele, is_universite)
    enseignant_fiche = "—"
    if classe and matiere_selectionnee and annee:
        aff = AffectationMatiere.objects.filter(
            classe=classe, matiere=matiere_selectionnee, annee=annee
        ).select_related('enseignant__user').first()
        if aff and aff.enseignant:
            enseignant_fiche = aff.enseignant.nom_complet
    if enseignant_fiche == "—" and lignes:
        auteurs = sorted({r['saisi_par'] for r in lignes if r['saisi_par'] and r['saisi_par'] != '—'})
        if len(auteurs) == 1:
            enseignant_fiche = auteurs[0]
        elif len(auteurs) > 1:
            enseignant_fiche = ", ".join(auteurs[:2]) + ("..." if len(auteurs) > 2 else "")

    if is_universite:
        matiere_fiche_label = (
            f"{ue_selectionnee.code} — {ue_selectionnee.nom} ({ue_selectionnee.credits} crédits ECTS)"
            if ue_selectionnee else "Toutes les Unités d'Enseignement (UE)"
        )
        periode_fiche_label = periode.libelle if periode else "Tous les semestres"
        if semestre_str:
            periode_fiche_label += f" — Semestre {semestre_str} (S{semestre_str})"
        titre_fiche = "FICHE OFFICIELLE DE NOTES — SYSTÈME LMD"
    elif is_premier_cycle:
        matiere_fiche_label = matiere_selectionnee.nom if matiere_selectionnee else "Toutes les matières"
        periode_fiche_label = f"Composition N° {numero} (Barème /10)"
        titre_fiche = "FICHE DE NOTES DE COMPOSITION — 1er CYCLE FONDAMENTAL"
    else:
        matiere_fiche_label = (
            f"{matiere_selectionnee.nom} (Coef. {matiere_selectionnee.coefficient})"
            if matiere_selectionnee else "Toutes les matières"
        )
        periode_fiche_label = periode.libelle if periode else "Toutes les périodes"
        titre_fiche = "FICHE D'ÉVALUATION & RELEVÉ DE NOTES PAR MATIÈRE"

    statut_labels_map = {
        '': 'Tous les élèves',
        'admis': 'Admis / Validés uniquement',
        'ajourne': 'Ajournés / Sous la moyenne',
        'rattrapage': 'En rattrapage / Proches moyenne',
        'manquant': 'Notes non saisies (manquantes)',
    }
    fiche_meta = {
        'titre_fiche': titre_fiche,
        'classe_label': f"{classe.nom} ({classe.niveau.nom})" if classe else "Toutes les classes",
        'filiere_label': (
            classe.filiere if (classe and classe.filiere)
            else (f"Série {classe.serie.code}" if (classe and classe.serie) else (cycle.nom if cycle else "Tous cycles"))
        ),
        'effectif_classe': classe.nombre_eleves if classe else len({r['eleve'].pk for r in lignes}),
        'matiere_label': matiere_fiche_label,
        'periode_label': periode_fiche_label,
        'enseignant_label': enseignant_fiche,
        'statut_filtre_label': statut_labels_map.get(statut, 'Tous les élèves'),
        'date_edition': timezone.now(),
    }

    # ── Génération des fichiers d'export si demandé ───────────────────────────
    if export_format == 'csv':
        return _generer_csv_detail(etab, annee, classe, periode, entete, fiche_meta, is_universite, is_premier_cycle, lignes, stats)
    elif export_format == 'xlsx_detail':
        return _generer_xlsx_detail(etab, annee, classe, periode, entete, fiche_meta, is_universite, is_premier_cycle, lignes, stats)
    elif export_format == 'xlsx_multi':
        return _generer_xlsx_multi_feuilles(etab, annee, classe, periode, entete, fiche_meta, is_universite, is_premier_cycle, lignes, stats)

    return render(request, 'notes/export_notes.html', {
        'classes': classes,
        'periodes': periodes,
        'matieres_disponibles': matieres_disponibles,
        'ues_disponibles': ues_disponibles,
        'semestres_disponibles': semestres_disponibles,
        'compo_numeros': compo_numeros,
        'classe': classe,
        'periode': periode,
        'annee': annee,
        'etab': etab,
        'modele': modele,
        'entete': entete,
        'fiche_meta': fiche_meta,
        'is_universite': is_universite,
        'is_premier_cycle': is_premier_cycle,
        'classe_id': classe_id,
        'periode_id': periode_id,
        'numero': numero,
        'matiere_id': matiere_id,
        'ue_id': ue_id,
        'semestre_str': semestre_str,
        'statut': statut,
        'sexe': sexe,
        'seuil_min_str': seuil_min_str,
        'seuil_max_str': seuil_max_str,
        'q': q,
        'tri': tri,
        'lignes': lignes[:500],
        'total_lignes_export': len(lignes),
        'stats': stats,
    })


