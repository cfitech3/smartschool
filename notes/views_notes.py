from django.shortcuts import render, redirect, get_object_or_404
from accounts.permissions import permission_required, role_required
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import Matiere, Periode, NotePeriode, LogModificationNote
from django.utils import timezone as dj_timezone
from etablissements.models import Classe, AnneeScolaire, ModeleDocument, AffectationMatiere
from eleves.models import Eleve
from decimal import Decimal
from core.cycle_filter import get_cycles_actifs_ids, get_classes_actives, get_eleves_actifs, get_inscriptions_actives


def require_etab(fn):
    def wrapper(request, *args, **kwargs):
        if not request.etablissement:
            return redirect('dashboard')
        return fn(request, *args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper


def peut_modifier_note(user, note_periode):
    """
    Sécurité : qui peut modifier une note ?
    - Super admin et admin : toujours
    - Enseignant : seulement ses propres matières affectées à cette classe
    - Surveillant : seulement la matière Conduite
    """
    if user.is_admin:
        return True, None
    if user.is_enseignant:
        # Vérifier que l'enseignant est affecté à cette matière/classe
        from etablissements.models import AffectationMatiere, AnneeScolaire
        etab = user.etablissement
        annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
        affectation = AffectationMatiere.objects.filter(
            enseignant__user=user,
            matiere=note_periode.matiere,
            classe=note_periode.classe,
            annee=annee
        ).exists()
        if affectation:
            return True, 'enseignant'
        return False, "Vous n'etes pas affecte a cette matiere pour cette classe."
    if user.is_surveillant:
        if note_periode.matiere.is_conduite:
            return True, 'surveillant'
        return False, "Le surveillant ne peut modifier que la note de conduite."
    return False, "Acces non autorise."


def enregistrer_log(note, user, champ, avant, apres):
    """Crée un log de modification."""
    LogModificationNote.objects.create(
        note_periode=note,
        modifie_par=user,
        role_modifiant=user.role,
        champ_modifie=champ,
        valeur_avant=str(avant) if avant is not None else '',
        valeur_apres=str(apres) if apres is not None else '',
        notif_envoyee=True if user.is_enseignant or user.is_surveillant else False,
    )


def calculer_bulletin(eleve, periode, matieres):
    """Calcule les lignes du bulletin malien."""
    lignes = []
    total_coeffic = Decimal('0')
    total_coef = 0

    for mat in matieres:
        note = NotePeriode.objects.filter(eleve=eleve, matiere=mat, periode=periode).first()
        if note:
            moy_finale = note.moyenne_finale
            moy_coeff  = note.moy_coeffic
            appre      = note.appreciation
            if moy_coeff is not None:
                total_coeffic += Decimal(str(moy_coeff))
                total_coef += mat.coefficient
            lignes.append({
                'matiere': mat,
                'moy_classe': float(note.moy_classe) if note.moy_classe is not None else None,
                'moy_compo': float(note.moy_compo) if note.moy_compo is not None else None,
                'note_conduite': float(note.note_conduite) if note.note_conduite is not None else None,
                'moyenne_finale': moy_finale,
                'moy_coeffic': moy_coeff,
                'appreciation': appre,
                'note_max_classe': float(note.note_max_classe),
                'note_max_compo': float(note.note_max_compo),
            })
        else:
            lignes.append({
                'matiere': mat,
                'moy_classe': None, 'moy_compo': None, 'note_conduite': None,
                'moyenne_finale': None, 'moy_coeffic': None, 'appreciation': '',
                'note_max_classe': 20, 'note_max_compo': 40,
            })

    moy_gen = round(float(total_coeffic) / total_coef, 2) if total_coef > 0 else None
    return lignes, moy_gen, float(total_coeffic), total_coef


@login_required
@permission_required('notes')
@require_etab
def saisie_notes_mali(request):
    etab = request.etablissement
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()

    # Filtrer les classes selon le rôle
    if request.user.is_enseignant:
        # Seulement les classes où l'enseignant est affecté
        aff_ids = AffectationMatiere.objects.filter(
            enseignant__user=request.user, annee=annee
        ).values_list('classe_id', flat=True)
        classes = Classe.objects.filter(etablissement=etab, annee=annee, pk__in=aff_ids)
    else:
        classes = get_classes_actives(etab, annee) if annee else []

    periodes = Periode.objects.filter(etablissement=etab, annee=annee) if annee else []

    # Filtrer les matières selon le rôle
    if request.user.is_enseignant:
        mat_ids = AffectationMatiere.objects.filter(
            enseignant__user=request.user, annee=annee
        ).values_list('matiere_id', flat=True)
        matieres = Matiere.objects.filter(etablissement=etab, pk__in=mat_ids, is_conduite=False)
    elif request.user.is_surveillant:
        matieres = Matiere.objects.filter(etablissement=etab, is_conduite=True)
    else:
        matieres = Matiere.objects.filter(etablissement=etab, is_conduite=False)

    classe_id  = request.GET.get('classe')
    periode_id = request.GET.get('periode')
    matiere_id = request.GET.get('matiere')

    classe  = get_object_or_404(Classe,  pk=classe_id,  etablissement=etab) if classe_id  else None
    periode = get_object_or_404(Periode, pk=periode_id, etablissement=etab) if periode_id else None
    matiere = get_object_or_404(Matiere, pk=matiere_id, etablissement=etab) if matiere_id else None

    eleves_data = []
    if classe and periode and matiere:
        inscriptions = classe.inscriptions.filter(is_active=True).select_related('eleve').order_by('eleve__nom')
        for insc in inscriptions:
            note = NotePeriode.objects.filter(eleve=insc.eleve, matiere=matiere, periode=periode, classe=classe).first()
            peut, raison = peut_modifier_note(request.user, note) if note else (True, None)
            eleves_data.append({'eleve': insc.eleve, 'note': note, 'peut_modifier': peut})

    if request.method == 'POST' and classe and periode and matiere:
        note_max_c = Decimal(request.POST.get('note_max_classe', '20'))
        note_max_n = Decimal(request.POST.get('note_max_compo', '40'))
        saved = 0
        modifiees = 0

        for insc in classe.inscriptions.filter(is_active=True).select_related('eleve'):
            if matiere.is_conduite:
                nc = request.POST.get(f'nc_{insc.eleve.pk}', '').strip()
                if nc:
                    valeur = Decimal(nc.replace(',','.'))
                    note_existante = NotePeriode.objects.filter(
                        eleve=insc.eleve, matiere=matiere, classe=classe, periode=periode
                    ).first()
                    if note_existante:
                        peut, raison = peut_modifier_note(request.user, note_existante)
                        if not peut:
                            messages.error(request, raison)
                            continue
                        avant = note_existante.note_conduite
                        enregistrer_log(note_existante, request.user, 'note_conduite', avant, valeur)
                        note_existante.note_conduite = valeur
                        note_existante.modifie_par = request.user
                        note_existante.save()
                        modifiees += 1
                    else:
                        note = NotePeriode.objects.create(
                            eleve=insc.eleve, matiere=matiere, classe=classe, periode=periode,
                            note_conduite=valeur, saisi_par=request.user
                        )
                        saved += 1
            else:
                mc = request.POST.get(f'mc_{insc.eleve.pk}', '').strip()
                mn = request.POST.get(f'mn_{insc.eleve.pk}', '').strip()
                if mc or mn:
                    note_existante = NotePeriode.objects.filter(
                        eleve=insc.eleve, matiere=matiere, classe=classe, periode=periode
                    ).first()
                    if note_existante:
                        peut, raison = peut_modifier_note(request.user, note_existante)
                        if not peut:
                            messages.error(request, raison)
                            continue
                        if mc:
                            avant = note_existante.moy_classe
                            enregistrer_log(note_existante, request.user, 'moy_classe', avant, Decimal(mc.replace(',','.')))
                            note_existante.moy_classe = Decimal(mc.replace(',','.'))
                        if mn:
                            avant = note_existante.moy_compo
                            enregistrer_log(note_existante, request.user, 'moy_compo', avant, Decimal(mn.replace(',','.')))
                            note_existante.moy_compo = Decimal(mn.replace(',','.'))
                        note_existante.modifie_par = request.user
                        note_existante.note_max_classe = note_max_c
                        note_existante.note_max_compo  = note_max_n
                        note_existante.save()
                        modifiees += 1
                    else:
                        defaults = {'note_max_classe': note_max_c, 'note_max_compo': note_max_n, 'saisi_par': request.user}
                        if mc: defaults['moy_classe'] = Decimal(mc.replace(',','.'))
                        if mn: defaults['moy_compo']  = Decimal(mn.replace(',','.'))
                        NotePeriode.objects.create(eleve=insc.eleve, matiere=matiere, classe=classe, periode=periode, **defaults)
                        saved += 1

        msg = f"{saved} note(s) creee(s)"
        if modifiees: msg += f", {modifiees} modifiee(s)"
        if modifiees and (request.user.is_enseignant or request.user.is_surveillant):
            msg += " — Le directeur a ete notifie"
        messages.success(request, msg)
        return redirect(f"{request.path}?classe={classe_id}&periode={periode_id}&matiere={matiere_id}")

    # Détecter le cycle de la classe pour adapter le formulaire
    cycle = None
    mode_calcul = 'compo'  # défaut
    if classe and classe.niveau and classe.niveau.cycle:
        cycle = classe.niveau.cycle
        mode_calcul = cycle.mode_calcul

    return render(request, 'notes/saisie_notes.html', {
        'classes': classes, 'periodes': periodes, 'matieres': matieres,
        'classe': classe, 'periode': periode, 'matiere': matiere,
        'eleves_data': eleves_data,
        'classe_id': classe_id, 'periode_id': periode_id, 'matiere_id': matiere_id,
        'is_conduite': matiere.is_conduite if matiere else False,
    })


@login_required
@require_etab
def releve_notes_classe(request):
    etab = request.etablissement
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
    classes = get_classes_actives(etab, annee) if annee else []
    periodes = Periode.objects.filter(etablissement=etab, annee=annee) if annee else []

    classe_id  = request.GET.get('classe')
    periode_id = request.GET.get('periode')
    classe  = get_object_or_404(Classe,  pk=classe_id,  etablissement=etab) if classe_id  else None
    periode = get_object_or_404(Periode, pk=periode_id, etablissement=etab) if periode_id else None

    tableau = []
    matieres = []
    if classe and periode:
        matieres = Matiere.objects.filter(etablissement=etab)
        inscriptions = classe.inscriptions.filter(is_active=True).select_related('eleve').order_by('eleve__nom')
        resultats = []
        for insc in inscriptions:
            lignes, moy, tc, tcoef = calculer_bulletin(insc.eleve, periode, matieres)
            resultats.append({'eleve': insc.eleve, 'moyenne': moy, 'lignes': lignes})
        resultats_avec_moy = [r for r in resultats if r['moyenne'] is not None]
        resultats_avec_moy.sort(key=lambda x: x['moyenne'], reverse=True)
        for i, r in enumerate(resultats_avec_moy, 1):
            r['rang'] = i
        tableau = resultats

    return render(request, 'notes/releve_classe.html', {
        'classes': classes, 'periodes': periodes,
        'classe': classe, 'periode': periode,
        'tableau': tableau, 'matieres': matieres,
        'classe_id': classe_id, 'periode_id': periode_id,
    })


@login_required
@require_etab
def bulletins_classe_mali(request):
    etab = request.etablissement
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
    classes = get_classes_actives(etab, annee) if annee else []
    periodes = Periode.objects.filter(etablissement=etab, annee=annee) if annee else []

    classe_id  = request.GET.get('classe')
    periode_id = request.GET.get('periode')
    classe  = get_object_or_404(Classe,  pk=classe_id,  etablissement=etab) if classe_id  else None
    periode = get_object_or_404(Periode, pk=periode_id, etablissement=etab) if periode_id else None

    resultats = []
    moy_premier = None
    matieres = Matiere.objects.filter(etablissement=etab)
    modele_actif = ModeleDocument.objects.filter(etablissement=etab, type_document='bulletin', is_actif=True).first()

    if classe and periode:
        inscriptions = classe.inscriptions.filter(is_active=True).select_related('eleve')
        for insc in inscriptions:
            _, moy, _, _ = calculer_bulletin(insc.eleve, periode, matieres)
            resultats.append({'eleve': insc.eleve, 'moyenne': moy})
        resultats.sort(key=lambda x: x['moyenne'] or 0, reverse=True)
        for i, r in enumerate(resultats, 1):
            r['rang'] = i
        if resultats and resultats[0]['moyenne']:
            moy_premier = resultats[0]['moyenne']

    return render(request, 'notes/bulletins_classe.html', {
        'classes': classes, 'periodes': periodes,
        'classe': classe, 'periode': periode,
        'resultats': resultats, 'moy_premier': moy_premier,
        'modele_actif': modele_actif,
        'classe_id': classe_id, 'periode_id': periode_id,
    })


@login_required
@require_etab
def bulletin_eleve(request, eleve_pk, periode_pk, modele_pk=None):
    etab = request.etablissement
    eleve = get_object_or_404(Eleve, pk=eleve_pk, etablissement=etab)
    periode = get_object_or_404(Periode, pk=periode_pk, etablissement=etab)
    annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
    inscription = eleve.get_inscription_active()
    matieres = Matiere.objects.filter(etablissement=etab).order_by('nom')

    if modele_pk:
        modele = get_object_or_404(ModeleDocument, pk=modele_pk, etablissement=etab)
    else:
        modele = ModeleDocument.objects.filter(etablissement=etab, type_document='bulletin', is_actif=True).first()

    lignes, moy_gen, total_coeffic, total_coef = calculer_bulletin(eleve, periode, matieres)

    rang = None
    moy_premier = None
    effectif = 0
    if inscription:
        classe = inscription.classe
        effectif = classe.inscriptions.filter(is_active=True).count()
        moyennes = []
        for insc in classe.inscriptions.filter(is_active=True).select_related('eleve'):
            _, moy, _, _ = calculer_bulletin(insc.eleve, periode, matieres)
            if moy is not None:
                moyennes.append((insc.eleve.pk, moy))
        moyennes.sort(key=lambda x: x[1], reverse=True)
        if moyennes:
            moy_premier = moyennes[0][1]
        for i, (epk, _) in enumerate(moyennes, 1):
            if epk == eleve.pk:
                rang = i
                break

    appre_dir = ''
    if moy_gen is not None:
        if moy_gen >= 16:   appre_dir = 'Excellent Travail'
        elif moy_gen >= 14: appre_dir = 'Bon Travail'
        elif moy_gen >= 12: appre_dir = 'Travail Assez Bien'
        elif moy_gen >= 10: appre_dir = 'Travail Passable'
        elif moy_gen >= 6:  appre_dir = 'Travail Insuffisant'
        else:               appre_dir = 'Travail Tres Insuffisant'

    return render(request, 'notes/bulletin_eleve.html', {
        'eleve': eleve, 'periode': periode, 'annee': annee,
        'etab': etab, 'modele': modele, 'inscription': inscription,
        'lignes': lignes, 'moy_generale': moy_gen,
        'total_coeffic': total_coeffic, 'total_coef': total_coef,
        'rang': rang, 'effectif': effectif, 'moy_premier': moy_premier,
        'appre_directeur': appre_dir,
        'today': dj_timezone.now().date(),
    })


@login_required
@require_etab
def logs_modifications(request):
    """Journal des modifications de notes — visible par admin et super admin."""
    if not request.user.is_admin:
        messages.error(request, "Acces reserve aux administrateurs.")
        return redirect('dashboard')
    etab = request.etablissement
    base_qs = LogModificationNote.objects.filter(
        note_periode__eleve__etablissement=etab
    )
    non_lus = base_qs.filter(notif_lue=False, notif_envoyee=True).count()
    logs = base_qs.select_related(
        'modifie_par', 'note_periode__eleve',
        'note_periode__matiere', 'note_periode__classe'
    ).order_by('-date_modif')[:100]
    # Marquer comme lus
    LogModificationNote.objects.filter(
        note_periode__eleve__etablissement=etab,
        notif_lue=False, notif_envoyee=True
    ).update(notif_lue=True)

    return render(request, 'notes/logs_modifications.html', {
        'logs': logs, 'non_lus': non_lus,
    })
