"""Vues dédiées au cycle université : saisie notes UE (Session 1, Rattrapage & Capitalisation) + relevé LMD."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from decimal import Decimal, InvalidOperation
from accounts.permissions import permission_required, is_etab_superieur, verifier_acces_bulletin, require_etab as req
from etablissements.models import Classe, AnneeScolaire, UEUniversite
from notes.models import NoteUE, Periode
from eleves.models import Eleve
from core.cycle_filter import get_classes_actives


def _filtrer_ues_filiere(ues_qs, classe):
    """Filtre un queryset UEUniversite selon la filière de la classe si des codes préfixés existent."""
    if not classe:
        return ues_qs
    filiere = (classe.filiere or '').strip()
    if not filiere and ' ' in classe.nom:
        filiere = classe.nom.split(' ', 1)[1].strip()
    if not filiere:
        return ues_qs
    PREFIX_MAP = {
        'droit': 'DROIT',
        'gestion': 'GEST',
        'informatique': 'INFO',
        'medecine': 'MED',
        'médecine': 'MED',
        'sciences': 'SCI',
    }
    prefixe = PREFIX_MAP.get(filiere.lower(), filiere[:4].upper())
    ues_filiere = ues_qs.filter(code__istartswith=prefixe)
    if ues_filiere.exists():
        return ues_filiere
    return ues_qs


def _parse_note_20(raw):
    """Convertit une chaîne en Decimal borné entre 0 et 20, ou lève ValueError."""
    val = Decimal(str(round(float(raw.replace(',', '.').strip()), 2)))
    if val < Decimal('0') or val > Decimal('20'):
        raise ValueError("La note doit être comprise entre 0 et 20.")
    return val


@login_required
@permission_required('notes')
@req
def saisie_notes_ue(request):
    etab = request.etablissement
    if not is_etab_superieur(etab):
        messages.error(request, "La saisie des notes UE est réservée aux établissements d'enseignement supérieur.")
        return redirect('saisie_notes_mali')
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
    classes = get_classes_actives(etab, annee, user=request.user).filter(
        niveau__cycle__type_cycle='universite'
    ).select_related('niveau', 'niveau__cycle').order_by('niveau__ordre', 'nom') if annee else Classe.objects.none()
    if request.user.is_enseignant and annee:
        from etablissements.models import AffectationMatiere
        from notes.models import EmploiDuTemps
        classes_aff_ids = set(AffectationMatiere.objects.filter(
            enseignant__user=request.user, annee=annee
        ).values_list('classe_id', flat=True))
        classes_edt_ids = set(EmploiDuTemps.objects.filter(
            enseignant=request.user, classe__etablissement=etab, classe__annee=annee
        ).values_list('classe_id', flat=True))
        classes_ue_ids = set(NoteUE.objects.filter(
            saisi_par=request.user, periode__annee=annee
        ).values_list('classe_id', flat=True))
        allowed_ids = classes_aff_ids | classes_edt_ids | classes_ue_ids
        classes = classes.filter(pk__in=allowed_ids)

    classe_id = request.GET.get('classe')
    periode_id = request.GET.get('periode')
    semestre_param = request.GET.get('semestre')
    session_mode = request.GET.get('session') or request.POST.get('session') or 'normale'
    if session_mode not in ('normale', 'rattrapage'):
        session_mode = 'normale'
    filtre_rattrapage = request.GET.get('filtre_rattrapage') == '1'

    classe = classes.filter(pk=classe_id).first() if classe_id else None
    periodes = Periode.objects.filter(etablissement=etab, annee=annee) if annee else []
    if periode_id and annee:
        periode = Periode.objects.filter(pk=periode_id, etablissement=etab, annee=annee).first()
    elif classe and annee:
        periode = periodes.filter(is_active=True).first() or periodes.first()
        if periode:
            periode_id = str(periode.pk)
    else:
        periode = None

    if semestre_param and semestre_param.isdigit():
        semestre = semestre_param
    elif classe:
        base_sem = classe.semestre_actif or ((classe.niveau.ordre - 1) * 2 + 1 if classe.niveau else 1)
        if base_sem % 2 == 0:
            base_sem -= 1
        semestre = str(base_sem + 1 if (periode and periode.numero == 2) else base_sem)
    else:
        semestre = '1'

    if request.method == 'POST' and classe and periode:
        if not periode.peut_saisir and not request.user.is_admin:
            messages.error(request, "La saisie est clôturée pour cette période. Contactez l'administration.")
            return redirect(f"{request.path}?classe={classe_id}&periode={periode_id}&semestre={semestre}&session={session_mode}")

        cycle_univ = classe.niveau.cycle
        ues = list(_filtrer_ues_filiere(
            UEUniversite.objects.filter(cycle=cycle_univ, semestre=int(semestre)),
            classe
        ))
        inscriptions = list(classe.inscriptions.filter(is_active=True).select_related('eleve'))
        eleves_ids = [i.eleve_id for i in inscriptions]

        # Action spéciale : report des UE capitalisées les années précédentes
        if request.POST.get('action') == 'importer_capitalisations':
            anciennes = NoteUE.objects.filter(
                eleve_id__in=eleves_ids, ue__in=ues, credits_valides=True
            ).exclude(periode=periode).order_by('-date_saisie')
            nb_cap = 0
            deja_traite = set()
            for anc in anciennes:
                key = (anc.eleve_id, anc.ue_id)
                if key in deja_traite:
                    continue
                deja_traite.add(key)
                note_cap = anc.note_retenue
                if note_cap is None or float(note_cap) < 10:
                    continue
                exist = NoteUE.objects.filter(
                    eleve_id=anc.eleve_id, ue_id=anc.ue_id, classe=classe, periode=periode
                ).first()
                if exist and exist.credits_valides:
                    continue
                obj, _ = NoteUE.objects.update_or_create(
                    eleve_id=anc.eleve_id, ue_id=anc.ue_id, classe=classe, periode=periode,
                    defaults={
                        'note': note_cap,
                        'saisi_par': request.user,
                    }
                )
                if '(Cap.)' not in (obj.mention or '') and 'Capitalisé' not in (obj.mention or ''):
                    obj.mention = f"{obj.mention} (Cap.)"[:20]
                    NoteUE.objects.filter(pk=obj.pk).update(mention=obj.mention)
                nb_cap += 1
            if nb_cap:
                messages.success(request, f"{nb_cap} UE capitalisée(s) d'une session/année antérieure reportée(s) avec succès.")
            else:
                messages.info(request, "Aucune UE capitalisée antérieure à reporter pour ces étudiants.")
            return redirect(f"{request.path}?classe={classe_id}&periode={periode_id}&semestre={semestre}&session={session_mode}")

        # Saisie Session 1 (normale) ou Session 2 (rattrapage)
        nb_saisies = 0
        for ue in ues:
            for insc in inscriptions:
                eleve = insc.eleve
                note_val = request.POST.get(f'note_{ue.pk}_{eleve.pk}')
                ratt_val = request.POST.get(f'ratt_{ue.pk}_{eleve.pk}')

                exist = NoteUE.objects.filter(
                    eleve=eleve, ue=ue, classe=classe, periode=periode
                ).first()

                if session_mode == 'rattrapage':
                    # En mode rattrapage : les UE déjà validées en Session 1 (>=10) sont verrouillées
                    if exist and exist.note is not None and float(exist.note) >= 10:
                        continue
                    if ratt_val is not None and ratt_val.strip() != '':
                        try:
                            ratt_dec = _parse_note_20(ratt_val)
                            if exist:
                                exist.note_rattrapage = ratt_dec
                                exist.saisi_par = request.user
                                exist.save()
                            else:
                                NoteUE.objects.create(
                                    eleve=eleve, ue=ue, classe=classe, periode=periode,
                                    note=None, note_rattrapage=ratt_dec, saisi_par=request.user
                                )
                            nb_saisies += 1
                        except (ValueError, InvalidOperation):
                            pass
                    elif ratt_val is not None and ratt_val.strip() == '' and exist and exist.note_rattrapage is not None:
                        exist.note_rattrapage = None
                        exist.saisi_par = request.user
                        exist.save()
                        nb_saisies += 1
                else:
                    # Mode normal : saisie Session 1 (+ rattrapage optionnel si saisi)
                    has_note = note_val is not None and note_val.strip() != ''
                    has_ratt = ratt_val is not None and ratt_val.strip() != ''
                    if not has_note and not has_ratt:
                        if exist and note_val is not None and note_val.strip() == '' and exist.note is not None:
                            exist.note = None
                            if ratt_val is not None and ratt_val.strip() == '':
                                exist.note_rattrapage = None
                            exist.saisi_par = request.user
                            exist.save()
                            nb_saisies += 1
                        continue
                    try:
                        note_dec = _parse_note_20(note_val) if has_note else (None if (note_val is not None and note_val.strip() == '') else (exist.note if exist else None))
                        ratt_dec = _parse_note_20(ratt_val) if has_ratt else (None if (ratt_val is not None and ratt_val.strip() == '') else (exist.note_rattrapage if exist else None))
                        if exist:
                            exist.note = note_dec
                            exist.note_rattrapage = ratt_dec
                            exist.saisi_par = request.user
                            exist.save()
                        else:
                            NoteUE.objects.create(
                                eleve=eleve, ue=ue, classe=classe, periode=periode,
                                note=note_dec, note_rattrapage=ratt_dec, saisi_par=request.user
                            )
                        nb_saisies += 1
                    except (ValueError, InvalidOperation):
                        pass

        messages.success(request, f"{nb_saisies} note(s) enregistrée(s) ({'2ᵉ session — Rattrapage' if session_mode == 'rattrapage' else '1ʳᵉ session — Normale'}).")
        q_filt = '&filtre_rattrapage=1' if filtre_rattrapage else ''
        return redirect(f"{request.path}?classe={classe_id}&periode={periode_id}&semestre={semestre}&session={session_mode}{q_filt}")

    ues_data = []
    eleves_list = []
    stats_session = {'valides_s1': 0, 'a_rattraper': 0, 'valides_ratt': 0, 'capitalisables': 0}

    if classe and classe.niveau and classe.niveau.cycle:
        cycle_univ = classe.niveau.cycle
        ues = list(_filtrer_ues_filiere(
            UEUniversite.objects.filter(cycle=cycle_univ, semestre=int(semestre)),
            classe
        ).order_by('code'))

        inscriptions = list(classe.inscriptions.filter(is_active=True).select_related('eleve'))
        tous_eleves = [i.eleve for i in inscriptions]

        notes_par_ue = {}
        for ue in ues:
            notes_existantes = {}
            if periode:
                for n in NoteUE.objects.filter(ue=ue, classe=classe, periode=periode, eleve__in=tous_eleves):
                    notes_existantes[n.eleve_id] = n
                    if n.note is not None and float(n.note) >= 10:
                        stats_session['valides_s1'] += 1
                    else:
                        stats_session['a_rattraper'] += 1
                        if n.note_rattrapage is not None and float(n.note_rattrapage) >= 10:
                            stats_session['valides_ratt'] += 1
                # Compter aussi les étudiants sans aucune note comme "à rattraper" si en S2
                stats_session['a_rattraper'] += max(0, len(tous_eleves) - len(notes_existantes))
            notes_par_ue[ue.pk] = notes_existantes

        # Détecter combien d'UE capitalisées antérieures peuvent être reportées
        if periode and tous_eleves and ues:
            deja_valides = set(
                NoteUE.objects.filter(classe=classe, periode=periode, credits_valides=True)
                .values_list('eleve_id', 'ue_id')
            )
            anciennes_pairs = set(
                NoteUE.objects.filter(eleve__in=tous_eleves, ue__in=ues, credits_valides=True)
                .exclude(periode=periode)
                .values_list('eleve_id', 'ue_id')
            )
            stats_session['capitalisables'] = len(anciennes_pairs - deja_valides)

        # Filtrer les étudiants en mode rattrapage si demandé
        if session_mode == 'rattrapage' and filtre_rattrapage and ues:
            for e in tous_eleves:
                a_besoin = False
                for ue in ues:
                    n = notes_par_ue[ue.pk].get(e.pk)
                    if not n or n.note is None or float(n.note) < 10:
                        a_besoin = True
                        break
                if a_besoin:
                    eleves_list.append(e)
        else:
            eleves_list = tous_eleves

        for ue in ues:
            notes_existantes = notes_par_ue[ue.pk]
            ues_data.append({
                'ue': ue,
                'notes': {e.pk: notes_existantes.get(e.pk) for e in eleves_list}
            })

    semestres_cycle = []
    if classe and classe.niveau and classe.niveau.cycle:
        semestres_cycle = list(
            _filtrer_ues_filiere(UEUniversite.objects.filter(cycle=classe.niveau.cycle), classe)
            .values_list('semestre', flat=True).distinct().order_by('semestre')
        )

    return render(request, 'notes/saisie_notes_ue.html', {
        'classes': classes, 'classe': classe, 'periodes': periodes, 'periode': periode,
        'classe_id': classe_id, 'periode_id': periode_id,
        'semestre': semestre, 'semestres_cycle': semestres_cycle,
        'session_mode': session_mode, 'filtre_rattrapage': filtre_rattrapage,
        'stats_session': stats_session,
        'ues_data': ues_data,
        'eleves_list': eleves_list,
    })


@login_required
@req
def releve_notes_lmd(request, eleve_pk, periode_pk):
    """Relevé de notes LMD (bulletin université) avec distinction S1 / Rattrapage / Capitalisation et QR signé."""
    from django.utils import timezone
    from etablissements.models import ModeleDocument
    from core.verification_qr import construire_contexte_qr

    etab = request.etablissement
    eleve = get_object_or_404(Eleve, pk=eleve_pk, etablissement=etab)

    refus = verifier_acces_bulletin(request, eleve)
    if refus:
        return refus

    periode = get_object_or_404(Periode, pk=periode_pk, etablissement=etab)
    annee = periode.annee
    insc = eleve.get_inscription_active()
    modele = ModeleDocument.objects.filter(etablissement=etab, type_document='releve_notes', is_actif=True).first()

    notes_ue = NoteUE.objects.filter(
        eleve=eleve, periode=periode
    ).select_related('ue').order_by('ue__semestre', 'ue__code')

    semestres = {}
    total_credits_obtenus = 0
    total_credits_s1 = 0
    total_credits_rattrapage = 0
    total_credits_requis = 0
    total_points = 0.0
    total_credits_notes = 0

    for n in notes_ue:
        s = n.ue.semestre
        if s not in semestres:
            semestres[s] = {
                'ues': [], 'credits_obtenus': 0, 'credits_requis': 0,
                'points': 0.0, 'credits_notes': 0, 'moyenne': None
            }
        # Qualifier la session de validation de l'UE
        if '(Cap.)' in (n.mention or ''):
            n.session_validation = 'Capitalisé'
        elif n.credits_valides and (n.note is None or float(n.note) < 10) and n.note_rattrapage is not None and float(n.note_rattrapage) >= 10:
            n.session_validation = 'Session 2 (Rattrapage)'
            total_credits_rattrapage += n.ue.credits
        elif n.credits_valides:
            n.session_validation = 'Session 1 (Normale)'
            total_credits_s1 += n.ue.credits
        else:
            n.session_validation = 'Ajourné (Rattrapage requis)'

        semestres[s]['ues'].append(n)
        semestres[s]['credits_requis'] += n.ue.credits
        if n.credits_valides:
            semestres[s]['credits_obtenus'] += n.ue.credits
            total_credits_obtenus += n.ue.credits
        total_credits_requis += n.ue.credits
        if n.note_retenue is not None:
            pts = float(n.note_retenue) * n.ue.credits
            semestres[s]['points'] += pts
            semestres[s]['credits_notes'] += n.ue.credits
            total_points += pts
            total_credits_notes += n.ue.credits

    for s, s_data in semestres.items():
        if s_data['credits_notes'] > 0:
            s_data['moyenne'] = round(s_data['points'] / s_data['credits_notes'], 2)
        if insc and insc.classe and insc.classe.niveau and insc.classe.niveau.cycle:
            ues_sem = _filtrer_ues_filiere(
                UEUniversite.objects.filter(cycle=insc.classe.niveau.cycle, semestre=s),
                insc.classe
            )
            cred_sem_programme = sum((u.credits or 0) for u in ues_sem)
            if cred_sem_programme > s_data['credits_requis']:
                total_credits_requis += (cred_sem_programme - s_data['credits_requis'])
                s_data['credits_requis'] = cred_sem_programme

    moy_generale = round(total_points / total_credits_notes, 2) if total_credits_notes > 0 else None

    mention = ''
    if moy_generale is not None:
        if moy_generale >= 16: mention = 'Très Bien'
        elif moy_generale >= 14: mention = 'Bien'
        elif moy_generale >= 12: mention = 'Assez Bien'
        elif moy_generale >= 10: mention = 'Passable'
        else: mention = 'Insuffisant — Ajourné'

    ctx = {
        'eleve': eleve, 'periode': periode, 'annee': annee,
        'etab': etab, 'modele': modele, 'inscription': insc,
        'notes_ue': notes_ue, 'semestres': semestres,
        'total_credits_obtenus': total_credits_obtenus,
        'total_credits_s1': total_credits_s1,
        'total_credits_rattrapage': total_credits_rattrapage,
        'total_credits_requis': total_credits_requis,
        'moy_generale': moy_generale, 'mention': mention,
        'today': timezone.now().date(),
    }
    ctx.update(construire_contexte_qr(
        request, 'lmd', eleve, annee=annee, periode=periode,
        extra={'moy': moy_generale}
    ))
    return render(request, 'notes/releve_lmd.html', ctx)
