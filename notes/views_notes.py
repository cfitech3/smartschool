from django.shortcuts import render, redirect, get_object_or_404
from accounts.permissions import permission_required, role_required
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import Matiere, Periode, NotePeriode, LogModificationNote, Composition
from django.utils import timezone as dj_timezone
from .services import calculer_bulletin
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


def peut_modifier_note(user, note_periode=None, matiere=None, classe=None, periode=None):
    """
    Sécurité : qui peut modifier/saisir une note ?
    - Super admin et admin : toujours
    - Si la période est clôturée : bloqué pour tout le monde sauf admin
    - Enseignant : seulement ses propres matières affectées à cette classe
    - Surveillant : seulement la matière Conduite
    """
    if user.is_admin:
        return True, None

    # Récupérer les objets depuis note_periode s'ils ne sont pas fournis
    if note_periode:
        matiere = matiere or note_periode.matiere
        classe = classe or note_periode.classe
        periode = periode or note_periode.periode

    # P2.2 : Vérifier la clôture de la période
    if periode and not periode.peut_saisir:
        return False, "La saisie est clôturée pour cette période. Contactez l'administration."
    if user.is_enseignant:
        # Vérifier que l'enseignant est affecté à cette matière/classe
        from etablissements.models import AffectationMatiere, AnneeScolaire
        etab = user.etablissement
        annee = AnneeScolaire.objects.filter(etablissement=etab, is_active=True).first()
        affectation = AffectationMatiere.objects.filter(
            enseignant__user=user,
            matiere=matiere,
            classe=classe,
            annee=annee
        ).exists()
        if affectation:
            return True, 'enseignant'
        return False, "Vous n'etes pas affecte a cette matiere pour cette classe."
    if user.is_surveillant:
        if matiere and matiere.is_conduite:
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


def calculer_rangs_classe(classe, periode, matieres):
    """
    Calcule les rangs de tous les élèves d'une classe en O(n) — un seul batch SQL.

    Au lieu de recalculer le bulletin de chaque élève individuellement (ce qui
    génère N × M requêtes SQL pour N élèves et M matières), on charge toutes
    les notes de la classe/période en une seule requête, puis on calcule
    les moyennes et le classement entièrement en Python.

    Retourne un dict : {eleve_pk: rang, ...}
    Exemple : {42: 1, 17: 2, 35: 3, ...}
    """
    # Charger toutes les notes de la classe/période en un seul appel DB
    toutes_notes = (
        NotePeriode.objects
        .filter(classe=classe, periode=periode)
        .select_related('matiere')
    )

    # Indexer les notes par (eleve_pk, matiere_pk) pour un accès O(1)
    index_notes = {(n.eleve_id, n.matiere_id): n for n in toutes_notes}

    # Récupérer les élèves inscrits et actifs dans la classe
    inscriptions = (
        classe.inscriptions
        .filter(is_active=True)
        .select_related('eleve')
        .only('eleve__id')
    )

    # Calculer la moyenne générale de chaque élève à partir de l'index
    moyennes = []  # liste de (eleve_pk, moyenne_generale)
    for insc in inscriptions:
        eleve_pk = insc.eleve_id
        total_coeffic = Decimal('0')
        total_coef = 0

        for mat in matieres:
            note = index_notes.get((eleve_pk, mat.pk))
            if note is not None:
                moy_coeff = note.moy_coeffic
                if moy_coeff is not None:
                    total_coeffic += Decimal(str(moy_coeff))
                    total_coef += mat.coefficient

        if total_coef > 0:
            moy_gen = round(float(total_coeffic) / total_coef, 2)
            moyennes.append((eleve_pk, moy_gen))

    # Trier par moyenne décroissante pour attribuer les rangs
    moyennes.sort(key=lambda x: x[1], reverse=True)

    # Construire le dictionnaire rang {eleve_pk: rang}
    rangs = {eleve_pk: rang for rang, (eleve_pk, _) in enumerate(moyennes, start=1)}
    return rangs



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

    # Détecter le cycle de la classe pour adapter le formulaire — déplacé
    # avant eleves_data car nécessaire pour savoir si on charge les
    # compositions multiples (1er cycle avec nb_compositions_trimestre > 1)
    cycle = None
    mode_calcul = 'compo'  # défaut
    if classe and classe.niveau and classe.niveau.cycle:
        cycle = classe.niveau.cycle
        mode_calcul = cycle.mode_calcul
    compositions_multiples = bool(cycle and cycle.utilise_compositions_multiples)
    compo_numeros = list(range(1, cycle.nb_compositions_trimestre + 1)) if compositions_multiples else []

    eleves_data = []
    if classe and periode and matiere:
        inscriptions = classe.inscriptions.filter(is_active=True).select_related('eleve').order_by('eleve__nom')
        for insc in inscriptions:
            note = NotePeriode.objects.filter(eleve=insc.eleve, matiere=matiere, periode=periode, classe=classe).first()
            peut, raison = peut_modifier_note(
                request.user, note_periode=note, matiere=matiere, classe=classe, periode=periode
            )
            item = {'eleve': insc.eleve, 'note': note, 'peut_modifier': peut, 'raison': raison}

            if compositions_multiples and not matiere.is_conduite:
                # 1er cycle : les compositions sont liées à l'année scolaire, pas à la période
                compos_existantes = {
                    c.numero: c for c in Composition.objects.filter(
                        eleve=insc.eleve, matiere=matiere, classe=classe, annee=annee
                    )
                }
                item['compos_list'] = [
                    {'numero': n, 'objet': compos_existantes.get(n)} for n in compo_numeros
                ]

            eleves_data.append(item)

    if request.method == 'POST' and classe and periode and matiere:
        note_max_c = Decimal(request.POST.get('note_max_classe', '20'))
        note_max_n = Decimal(request.POST.get('note_max_compo', '40'))
        saved = 0
        modifiees = 0

        for insc in classe.inscriptions.filter(is_active=True).select_related('eleve'):
            if compositions_multiples and not matiere.is_conduite:
                # ── Compositions multiples (1er cycle, N compositions/trimestre) ──
                # Chaque composition est indépendante : on la crée/modifie/vide
                # individuellement. Composition.save() recalcule automatiquement
                # NotePeriode.moy_compo — voir notes/models.py.
                mc = request.POST.get(f'mc_{insc.eleve.pk}', '').strip()
                note_existante = NotePeriode.objects.filter(
                    eleve=insc.eleve, matiere=matiere, classe=classe, periode=periode
                ).first()
                peut, raison = peut_modifier_note(
                    request.user, note_periode=note_existante, matiere=matiere, classe=classe, periode=periode
                )
                if not peut:
                    messages.error(request, raison)
                    continue

                from decimal import InvalidOperation
                touche = False

                # Moy. classe (identique au cas standard)
                if mc:
                    try:
                        val_mc = Decimal(mc.replace(',', '.'))
                    except InvalidOperation:
                        messages.warning(request, f"Format de note classe invalide pour {insc.eleve.nom_complet}.")
                        val_mc = None
                    if val_mc is not None and 0 <= val_mc <= note_max_c:
                        note_existante = note_existante or NotePeriode.objects.create(
                            eleve=insc.eleve, matiere=matiere, classe=classe, periode=periode,
                            note_max_classe=note_max_c, note_max_compo=note_max_n, saisi_par=request.user,
                        )
                        avant = note_existante.moy_classe
                        note_existante.moy_classe = val_mc
                        note_existante.note_max_classe = note_max_c
                        note_existante.modifie_par = request.user
                        note_existante.save()
                        if avant != val_mc:
                            enregistrer_log(note_existante, request.user, 'moy_classe', avant, val_mc)
                        touche = True

                # Chaque composition individuelle
                for numero in compo_numeros:
                    cc = request.POST.get(f'compo{numero}_{insc.eleve.pk}', '').strip()
                    if not cc:
                        continue
                    try:
                        val_cc = Decimal(cc.replace(',', '.'))
                    except InvalidOperation:
                        messages.warning(request, f"Format Compo {numero} invalide pour {insc.eleve.nom_complet}.")
                        continue
                    if not (0 <= val_cc <= 10):
                        messages.warning(request, f"Compo {numero} hors plage (0-10) ignorée pour {insc.eleve.nom_complet}.")
                        continue
                    # Lier la composition à l'année scolaire (pas à la période)
                    # et stocker avec note_max=10
                    Composition.objects.update_or_create(
                        eleve=insc.eleve, matiere=matiere, classe=classe, annee=annee, numero=numero,
                        defaults={'note': val_cc, 'note_max': 10, 'saisi_par': request.user},
                    )
                    touche = True

                if touche:
                    modifiees += 1
                continue  # passe au prochain élève, on ne retombe pas dans les branches ci-dessous

            if matiere.is_conduite:
                nc = request.POST.get(f'nc_{insc.eleve.pk}', '').strip()
                if nc:
                    from decimal import InvalidOperation
                    try:
                        valeur = Decimal(nc.replace(',','.'))
                    except InvalidOperation:
                        messages.warning(request, f"Format de note conduite invalide pour {insc.eleve.nom_complet}.")
                        continue
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
                        peut, raison = peut_modifier_note(request.user, matiere=matiere, classe=classe, periode=periode)
                        if not peut:
                            messages.error(request, raison)
                            continue
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
                            from decimal import InvalidOperation
                            try:
                                val_mc = Decimal(mc.replace(',','.'))
                            except InvalidOperation:
                                messages.warning(request, f"Format de note classe invalide pour {insc.eleve.nom_complet}.")
                                continue
                            if 0 <= val_mc <= note_max_c:
                                avant = note_existante.moy_classe
                                enregistrer_log(note_existante, request.user, 'moy_classe', avant, val_mc)
                                note_existante.moy_classe = val_mc
                            else:
                                messages.warning(request, f"Note classe hors plage (0-{note_max_c}) ignoree pour {insc.eleve.nom_complet}.")
                        if mn:
                            from decimal import InvalidOperation
                            try:
                                val_mn = Decimal(mn.replace(',','.'))
                            except InvalidOperation:
                                messages.warning(request, f"Format de note compo invalide pour {insc.eleve.nom_complet}.")
                                continue
                            if 0 <= val_mn <= note_max_n:
                                avant = note_existante.moy_compo
                                enregistrer_log(note_existante, request.user, 'moy_compo', avant, val_mn)
                                note_existante.moy_compo = val_mn
                            else:
                                messages.warning(request, f"Note compo hors plage (0-{note_max_n}) ignoree pour {insc.eleve.nom_complet}.")
                        note_existante.modifie_par = request.user
                        note_existante.note_max_classe = note_max_c
                        note_existante.note_max_compo  = note_max_n
                        note_existante.save()
                        modifiees += 1
                    else:
                        peut, raison = peut_modifier_note(request.user, matiere=matiere, classe=classe, periode=periode)
                        if not peut:
                            messages.error(request, raison)
                            continue
                        defaults = {'note_max_classe': note_max_c, 'note_max_compo': note_max_n, 'saisi_par': request.user}
                        if mc:
                            from decimal import InvalidOperation
                            try:
                                val_mc = Decimal(mc.replace(',','.'))
                            except InvalidOperation:
                                messages.warning(request, f"Format de note classe invalide pour {insc.eleve.nom_complet}.")
                                continue
                            if 0 <= val_mc <= note_max_c:
                                defaults['moy_classe'] = val_mc
                        if mn:
                            from decimal import InvalidOperation
                            try:
                                val_mn = Decimal(mn.replace(',','.'))
                            except InvalidOperation:
                                messages.warning(request, f"Format de note compo invalide pour {insc.eleve.nom_complet}.")
                                continue
                            if 0 <= val_mn <= note_max_n:
                                defaults['moy_compo'] = val_mn
                        NotePeriode.objects.create(eleve=insc.eleve, matiere=matiere, classe=classe, periode=periode, **defaults)
                        saved += 1

        msg = f"{saved} note(s) creee(s)"
        if modifiees: msg += f", {modifiees} modifiee(s)"
        if modifiees and (request.user.is_enseignant or request.user.is_surveillant):
            msg += " — Le directeur a ete notifie"
        messages.success(request, msg)
        return redirect(f"{request.path}?classe={classe_id}&periode={periode_id}&matiere={matiere_id}")

    return render(request, 'notes/saisie_notes.html', {
        'classes': classes, 'periodes': periodes, 'matieres': matieres,
        'classe': classe, 'periode': periode, 'matiere': matiere,
        'eleves_data': eleves_data,
        'compositions_multiples': compositions_multiples,
        'compo_numeros': compo_numeros,
        'classe_id': classe_id, 'periode_id': periode_id, 'matiere_id': matiere_id,
        'is_conduite': matiere.is_conduite if matiere else False,
    })


@login_required
@permission_required('bulletins')
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
        from .services import get_matieres_pour_classe
        matieres = get_matieres_pour_classe(classe, periode)
        # P2.5 : Préchargement des notes pour éviter N+1 requêtes
        toutes_notes = NotePeriode.objects.filter(classe=classe, periode=periode)
        index_notes = {(n.eleve_id, n.matiere_id): n for n in toutes_notes}

        inscriptions = classe.inscriptions.filter(is_active=True).select_related('eleve').order_by('eleve__nom')
        resultats = []
        for insc in inscriptions:
            lignes, moy, tc, tcoef = calculer_bulletin(insc.eleve, periode, matieres, index_notes=index_notes)
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
@permission_required('bulletins')
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

    # Détecter le cycle de la classe
    cycle = None
    is_premier_cycle = False
    if classe and classe.niveau and classe.niveau.cycle:
        cycle = classe.niveau.cycle
        is_premier_cycle = cycle.is_premier_cycle and cycle.utilise_compositions_multiples

    resultats = []
    moy_premier = None
    matieres = Matiere.objects.filter(etablissement=etab)
    modele_actif = ModeleDocument.objects.filter(etablissement=etab, type_document='bulletin', is_actif=True).first()

    if classe and periode:
        inscriptions = classe.inscriptions.filter(is_active=True).select_related('eleve')

        if is_premier_cycle and annee:
            # 1er cycle : calculer les moyennes depuis les Compositions /10
            from notes.services import calculer_bulletin_composition
            nb_compos = cycle.nb_compositions_trimestre
            for insc in inscriptions:
                # Moyenne sur toutes les compositions de l'année
                total_moy = 0
                nb_valides = 0
                for numero in range(1, nb_compos + 1):
                    _, moy_compo, _, _ = calculer_bulletin_composition(insc.eleve, annee, numero, matieres)
                    if moy_compo is not None:
                        total_moy += moy_compo
                        nb_valides += 1
                moy = round(total_moy / nb_valides, 2) if nb_valides > 0 else None
                resultats.append({'eleve': insc.eleve, 'moyenne': moy})
        else:
            # Autres cycles : NotePeriode classique
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
        'is_premier_cycle': is_premier_cycle,
        'annee': annee,
        'cycle': cycle,
    })


@login_required
@require_etab
def bulletin_eleve(request, eleve_pk, periode_pk, modele_pk=None):
    etab = request.etablissement
    eleve = get_object_or_404(Eleve, pk=eleve_pk, etablissement=etab)
    
    # Sécurité IDOR Famille
    if request.user.role in ['parent', 'eleve']:
        from core.views_espace_famille import get_eleves_accessibles
        eleves_ok = get_eleves_accessibles(request.user).values_list('pk', flat=True)
        if eleve.pk not in eleves_ok:
            messages.error(request, "Accès refusé. Ce bulletin ne vous appartient pas.")
            return redirect('dashboard')

    periode = get_object_or_404(Periode, pk=periode_pk, etablissement=etab)
    annee = periode.annee
    inscription = eleve.get_inscription_active()
    
    from .services import get_matieres_pour_eleve
    classe_pour_matieres = inscription.classe if inscription else None
    matieres = get_matieres_pour_eleve(eleve, periode, classe_pour_matieres)

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

        # Calcul de rang O(n) : un seul batch SQL pour toute la classe,
        # au lieu de recalculer le bulletin de chaque élève individuellement.
        rangs_classe = calculer_rangs_classe(classe, periode, matieres)
        rang = rangs_classe.get(eleve.pk)

        # Moyenne du premier : on relit le résultat trié depuis rangs_classe
        if rangs_classe:
            # Retrouver la moyenne du 1er élève classé
            # (rang 1 = clé dont la valeur vaut 1)
            pk_premier = next(
                (pk for pk, r in rangs_classe.items() if r == 1), None
            )
            if pk_premier is not None:
                _, moy_premier, _, _ = calculer_bulletin(
                    Eleve.objects.get(pk=pk_premier), periode, matieres
                )

    appre_dir = ''
    if moy_gen is not None:
        if moy_gen >= 8:   appre_dir = 'Excellent Travail'
        elif moy_gen >= 7: appre_dir = 'Bon Travail'
        elif moy_gen >= 6: appre_dir = 'Travail Assez Bien'
        elif moy_gen >= 5: appre_dir = 'Travail Passable'
        elif moy_gen >= 3: appre_dir = 'Travail Insuffisant'
        else:              appre_dir = 'Travail Tres Insuffisant'

    return render(request, 'notes/bulletin_eleve.html', {
        'eleve': eleve, 'annee': annee,
        'etab': etab, 'modele': modele, 'inscription': inscription,
        'lignes': lignes, 'moy_generale': moy_gen,
        'total_coeffic': total_coeffic, 'total_coef': total_coef,
        'rang': rang, 'effectif': effectif, 'moy_premier': moy_premier,
        'appre_directeur': appre_dir,
        'today': dj_timezone.now().date(),
    })


@login_required
def bulletin_composition(request, eleve_pk, annee_pk, numero):
    """
    Bulletin d'une composition individuelle (1er cycle fondamental,
    établissements avec compositions multiples par trimestre). Distinct
    du bulletin trimestriel classique : affiche uniquement la note
    obtenue à CETTE composition précise, matière par matière.
    """
    etab  = request.etablissement
    eleve = get_object_or_404(Eleve, pk=eleve_pk, etablissement=etab)

    # Sécurité IDOR Famille — même contrôle que bulletin_eleve
    if request.user.role in ['parent', 'eleve']:
        from core.views_espace_famille import get_eleves_accessibles
        eleves_ok = get_eleves_accessibles(request.user).values_list('pk', flat=True)
        if eleve.pk not in eleves_ok:
            messages.error(request, "Accès refusé. Ce bulletin ne vous appartient pas.")
            return redirect('dashboard')

    annee = get_object_or_404(AnneeScolaire, pk=annee_pk, etablissement=etab)
    inscription = eleve.get_inscription_active()

    # Vérifier que le cycle de l'élève utilise bien les compositions multiples
    cycle = None
    if inscription and inscription.classe.niveau and inscription.classe.niveau.cycle:
        cycle = inscription.classe.niveau.cycle
    if not cycle or not cycle.is_premier_cycle:
        messages.error(request, "Le bulletin de composition /10 est réservé au 1er cycle fondamental.")
        return redirect('bulletins_classe_mali')
    if not cycle.utilise_compositions_multiples:
        messages.error(request, "Ce cycle n'a pas de compositions configurées.")
        return redirect('bulletins_classe_mali')
    if numero < 1 or numero > cycle.nb_compositions_trimestre:
        messages.error(request, f"Composition {numero} invalide pour ce cycle ({cycle.nb_compositions_trimestre} compositions).")
        return redirect('bulletins_classe_mali')

    from .services import get_matieres_pour_eleve, calculer_bulletin_composition
    # Pour le 1er cycle, on récupère les matières via l'année scolaire
    matieres = get_matieres_pour_eleve(eleve, annee, inscription.classe if inscription else None)

    modele = ModeleDocument.objects.filter(etablissement=etab, type_document='bulletin', is_actif=True).first()

    lignes, moy_gen, total_coeffic, total_coef = calculer_bulletin_composition(eleve, annee, numero, matieres)

    rang, effectif, moy_premier = None, 0, None
    if inscription:
        classe = inscription.classe
        effectif = classe.inscriptions.filter(is_active=True).count()

    appre_dir = ''
    if moy_gen is not None:
        if moy_gen >= 8:   appre_dir = 'Excellent Travail'
        elif moy_gen >= 7: appre_dir = 'Bon Travail'
        elif moy_gen >= 6: appre_dir = 'Travail Assez Bien'
        elif moy_gen >= 5: appre_dir = 'Travail Passable'
        elif moy_gen >= 3: appre_dir = 'Travail Insuffisant'
        else:              appre_dir = 'Travail Tres Insuffisant'

    return render(request, 'notes/bulletin_composition.html', {
        'eleve': eleve, 'annee': annee,
        'etab': etab, 'modele': modele, 'inscription': inscription,
        'numero': numero, 'nb_compositions': cycle.nb_compositions_trimestre,
        'compo_range': range(1, cycle.nb_compositions_trimestre + 1),
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

