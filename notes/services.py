import logging
from decimal import Decimal, ROUND_HALF_UP
from .models import NotePeriode

logger = logging.getLogger(__name__)


def get_coefficients_map(classe, matieres):
    """
    Retourne un dict {matiere_pk: coefficient_effectif} en 1 à 2 requêtes SQL.
    Priorité : MatiereSerieCoef (si série lycée) -> MatiereCycle (si cycle) -> Matiere.coefficient.
    """
    coefs = {m.pk: m.coefficient for m in matieres}
    if not classe:
        return coefs
    try:
        from etablissements.models import MatiereCycle, MatiereSerieCoef
        if classe.niveau_id and classe.niveau and classe.niveau.cycle_id:
            for mat_id, c in MatiereCycle.objects.filter(
                cycle_id=classe.niveau.cycle_id, matiere__in=matieres
            ).values_list('matiere_id', 'coefficient'):
                coefs[mat_id] = c
        if classe.serie_id:
            for mat_id, c in MatiereSerieCoef.objects.filter(
                serie_id=classe.serie_id, matiere__in=matieres
            ).values_list('matiere_id', 'coefficient'):
                coefs[mat_id] = c
    except Exception:
        logger.warning("Erreur lors du chargement des coefficients pour la classe %s", getattr(classe, 'pk', None), exc_info=True)
    return coefs


def calculer_bulletin(eleve, periode, matieres, index_notes=None, classe=None, coefs_map=None):
    """
    Calcule le bulletin (commun ou malien).
    Si index_notes (dict {(eleve_id, matiere_id): note}) est fourni,
    évite les requêtes SQL (utile pour les traitements par lot O(n)).
    Retourne: lignes, moyenne_generale, total_coeffic, total_coef
    """
    lignes = []
    total_coeffic = Decimal('0')
    total_coef = 0
    if coefs_map is None and classe is not None:
        coefs_map = get_coefficients_map(classe, matieres)

    for mat in matieres:
        if index_notes is not None:
            note = index_notes.get((eleve.pk, mat.pk))
        else:
            qs_note = NotePeriode.objects.filter(eleve=eleve, matiere=mat, periode=periode).select_related('classe__niveau')
            note = (qs_note.filter(classe=classe).first() if classe is not None else None) or qs_note.order_by('-date_modif', '-pk').first()
        if coefs_map is not None:
            coef = coefs_map.get(mat.pk, mat.coefficient)
        elif note is not None:
            coef = note.coefficient_effectif
        else:
            coef = mat.coefficient
        if note:
            note._coef_cache = coef
            moy_finale = note.moyenne_finale
            moy_coeff  = round(moy_finale * coef, 2) if moy_finale is not None else None
            appre      = note.appreciation
            if moy_coeff is not None:
                total_coeffic += Decimal(str(moy_coeff))
                total_coef += coef
            lignes.append({
                'matiere': mat,
                'coef': coef,
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
                'coef': coef,
                'moy_classe': None, 'moy_compo': None, 'note_conduite': None,
                'moyenne_finale': None, 'moy_coeffic': None, 'appreciation': '',
                'note_max_classe': 20.0, 'note_max_compo': 40.0,
            })

    moy_gen = None
    if total_coef > 0:
        moy_gen = float(
            (total_coeffic / Decimal(str(total_coef))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        )

    # Conduite toujours en dernière ligne du bulletin
    lignes.sort(key=lambda l: (1 if l['matiere'].is_conduite else 0, l['matiere'].nom))

    return lignes, moy_gen, total_coeffic, total_coef


def calculer_bulletin_composition(eleve, annee, numero, matieres, index_compos=None):
    """
    Calcule le 'bulletin de composition' pour le 1er cycle fondamental.
    Si `index_compos` ({(eleve_id, matiere_id): Composition}) est fourni,
    s'exécute en 0 requête SQL par élève.
    """
    from .models import Composition

    lignes = []
    total_coeffic = Decimal('0')
    total_coef = 0

    if index_compos is not None:
        compos_map = {m.pk: index_compos.get((eleve.pk, m.pk)) for m in matieres}
    else:
        compos_map = {
            c.matiere_id: c
            for c in Composition.objects.filter(eleve=eleve, annee=annee, numero=numero, matiere__in=matieres)
        }

    for mat in matieres:
        if mat.is_conduite:
            continue  # la conduite n'a pas de composition individuelle
        compo = compos_map.get(mat.pk)

        # Coef forcé à 1 pour le 1er cycle
        coef = 1

        if compo and compo.note is not None:
            # note_max est 10 par défaut pour le 1er cycle
            note_sur_10 = round((float(compo.note) / float(compo.note_max)) * 10, 2)
            moy_coeff = round(note_sur_10 * coef, 2)  # coef=1 => moy_coeff = note
            total_coeffic += Decimal(str(moy_coeff))
            total_coef += coef
            appre = (
                'Tres-Bien'  if note_sur_10 >= 8 else
                'Bien'       if note_sur_10 >= 7 else
                'Assez-Bien' if note_sur_10 >= 6 else
                'Passable'   if note_sur_10 >= 5 else
                'Mal'        if note_sur_10 >= 3 else 'Tres Mal'
            )
            lignes.append({
                'matiere': mat,
                'note': note_sur_10,
                'moy_coeffic': moy_coeff,
                'appreciation': appre,
                'coef': coef,
            })
        else:
            lignes.append({
                'matiere': mat, 'note': None, 'moy_coeffic': None,
                'appreciation': '', 'coef': coef,
            })

    moy_gen = None
    if total_coef > 0:
        moy_gen = float(
            (total_coeffic / Decimal(str(total_coef))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        )

    lignes.sort(key=lambda l: l['matiere'].nom)
    return lignes, moy_gen, total_coeffic, total_coef


def get_matieres_pour_eleve(eleve, annee_ou_periode, classe=None):
    """
    Retourne les matières de l'élève.
    annee_ou_periode peut être une AnneeScolaire (1er cycle avec Composition)
    ou une Periode (autres cycles avec NotePeriode).
    """
    from etablissements.models import AffectationMatiere, AnneeScolaire
    from .models import Matiere, NotePeriode
    mat_ids = set()

    if isinstance(annee_ou_periode, AnneeScolaire):
        # 1er cycle : on récupère les matières via les affectations de la classe
        annee = annee_ou_periode
        if classe:
            mat_ids.update(
                AffectationMatiere.objects.filter(classe=classe, annee=annee)
                .values_list('matiere_id', flat=True)
            )
    else:
        # Autres cycles : annee_ou_periode est une Periode
        periode = annee_ou_periode
        if classe:
            mat_ids.update(
                AffectationMatiere.objects.filter(classe=classe, annee=periode.annee)
                .values_list('matiere_id', flat=True)
            )
        mat_ids.update(
            NotePeriode.objects.filter(eleve=eleve, periode=periode)
            .values_list('matiere_id', flat=True)
        )

    return Matiere.objects.filter(id__in=mat_ids).order_by('nom')


def enregistrer_log(note, user, champ, avant, apres):
    """Crée un log de modification de note."""
    from .models import LogModificationNote
    LogModificationNote.objects.create(
        note_periode=note,
        modifie_par=user,
        role_modifiant=user.role,
        champ_modifie=champ,
        valeur_avant=str(avant) if avant is not None else '',
        valeur_apres=str(apres) if apres is not None else '',
        notif_envoyee=bool(user.is_enseignant or user.is_surveillant),
    )


def _attribuer_rangs_ex_aequo(moyennes):
    """Trie une liste (eleve_pk, moyenne) décroissante et retourne {eleve_pk: rang}."""
    moyennes.sort(key=lambda x: x[1], reverse=True)
    rangs = {}
    prev_moy = None
    prev_rang = 0
    for idx, (eleve_pk, moy_val) in enumerate(moyennes, start=1):
        if moy_val != prev_moy:
            prev_rang = idx
            prev_moy = moy_val
        rangs[eleve_pk] = prev_rang
    return rangs


def calculer_rangs_classe(classe, periode, matieres):
    """Calcule les rangs de tous les élèves d'une classe en un seul batch SQL."""
    toutes_notes = (
        NotePeriode.objects
        .filter(classe=classe, periode=periode)
        .select_related('matiere')
    )
    index_notes = {(n.eleve_id, n.matiere_id): n for n in toutes_notes}
    inscriptions = (
        classe.inscriptions
        .filter(is_active=True)
        .select_related('eleve')
        .only('eleve__id')
    )
    coefs_map = get_coefficients_map(classe, matieres)
    moyennes = []
    for insc in inscriptions:
        eleve_pk = insc.eleve_id
        total_coeffic = Decimal('0')
        total_coef = 0
        for mat in matieres:
            note = index_notes.get((eleve_pk, mat.pk))
            if note is not None:
                coef = coefs_map.get(mat.pk, mat.coefficient)
                note._coef_cache = coef
                moy_finale = note.moyenne_finale
                if moy_finale is not None:
                    moy_coeff = round(moy_finale * coef, 2)
                    total_coeffic += Decimal(str(moy_coeff))
                    total_coef += coef
        if total_coef > 0:
            moy_gen = float(
                (total_coeffic / Decimal(str(total_coef))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            )
            moyennes.append((eleve_pk, moy_gen))
    return _attribuer_rangs_ex_aequo(moyennes)


def calculer_rangs_classe_composition(classe, annee, numero, matieres):
    """Calcule les rangs de tous les élèves d'une classe pour une composition 1er cycle."""
    from .models import Composition
    toutes_compos = (
        Composition.objects
        .filter(classe=classe, annee=annee, numero=numero)
        .select_related('matiere')
    )
    index_compos = {(c.eleve_id, c.matiere_id): c for c in toutes_compos}
    inscriptions = (
        classe.inscriptions
        .filter(is_active=True)
        .select_related('eleve')
        .only('eleve__id')
    )
    moyennes = []
    for insc in inscriptions:
        eleve_pk = insc.eleve_id
        total_coeffic = Decimal('0')
        total_coef = 0
        for mat in matieres:
            if mat.is_conduite:
                continue
            compo = index_compos.get((eleve_pk, mat.pk))
            if compo and compo.note is not None and compo.note_max:
                note_sur_10 = (Decimal(str(compo.note)) / Decimal(str(compo.note_max))) * Decimal('10')
                total_coeffic += note_sur_10.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                total_coef += 1
        if total_coef > 0:
            moy_gen = float(
                (total_coeffic / Decimal(str(total_coef))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            )
            moyennes.append((eleve_pk, moy_gen))
    return _attribuer_rangs_ex_aequo(moyennes)


def get_matieres_pour_classe(classe, periode=None):
    from etablissements.models import AffectationMatiere
    from .models import Matiere, NotePeriode, Composition
    mat_ids = set()
    annee = periode.annee if periode else classe.annee

    if annee:
        mat_ids.update(
            AffectationMatiere.objects.filter(classe=classe, annee=annee)
            .values_list('matiere_id', flat=True)
        )

    if periode:
        mat_ids.update(
            NotePeriode.objects.filter(classe=classe, periode=periode)
            .values_list('matiere_id', flat=True)
        )
    elif annee:
        mat_ids.update(
            Composition.objects.filter(classe=classe, annee=annee)
            .values_list('matiere_id', flat=True)
        )

    if not mat_ids:
        return Matiere.objects.filter(etablissement=classe.etablissement).order_by('nom')

    return Matiere.objects.filter(id__in=mat_ids).order_by('nom')


def enregistrer_log(note, user, champ, avant, apres):
    """Crée un log de modification de note."""
    from .models import LogModificationNote
    LogModificationNote.objects.create(
        note_periode=note,
        modifie_par=user,
        role_modifiant=user.role,
        champ_modifie=champ,
        valeur_avant=str(avant) if avant is not None else '',
        valeur_apres=str(apres) if apres is not None else '',
        notif_envoyee=bool(user.is_enseignant or user.is_surveillant),
    )


def _attribuer_rangs_ex_aequo(moyennes):
    """Trie une liste (eleve_pk, moyenne) décroissante et retourne {eleve_pk: rang}."""
    moyennes.sort(key=lambda x: x[1], reverse=True)
    rangs = {}
    prev_moy = None
    prev_rang = 0
    for idx, (eleve_pk, moy_val) in enumerate(moyennes, start=1):
        if moy_val != prev_moy:
            prev_rang = idx
            prev_moy = moy_val
        rangs[eleve_pk] = prev_rang
    return rangs


def calculer_rangs_classe(classe, periode, matieres):
    """Calcule les rangs de tous les élèves d'une classe en un seul batch SQL."""
    toutes_notes = (
        NotePeriode.objects
        .filter(classe=classe, periode=periode)
        .select_related('matiere')
    )
    index_notes = {(n.eleve_id, n.matiere_id): n for n in toutes_notes}
    inscriptions = (
        classe.inscriptions
        .filter(is_active=True)
        .select_related('eleve')
        .only('eleve__id')
    )
    coefs_map = get_coefficients_map(classe, matieres)
    moyennes = []
    for insc in inscriptions:
        eleve_pk = insc.eleve_id
        total_coeffic = Decimal('0')
        total_coef = 0
        for mat in matieres:
            note = index_notes.get((eleve_pk, mat.pk))
            if note is not None:
                coef = coefs_map.get(mat.pk, mat.coefficient)
                note._coef_cache = coef
                moy_finale = note.moyenne_finale
                if moy_finale is not None:
                    moy_coeff = round(moy_finale * coef, 2)
                    total_coeffic += Decimal(str(moy_coeff))
                    total_coef += coef
        if total_coef > 0:
            moy_gen = float(
                (total_coeffic / Decimal(str(total_coef))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            )
            moyennes.append((eleve_pk, moy_gen))
    return _attribuer_rangs_ex_aequo(moyennes)


def calculer_rangs_classe_composition(classe, annee, numero, matieres):
    """Calcule les rangs de tous les élèves d'une classe pour une composition 1er cycle."""
    from .models import Composition
    toutes_compos = (
        Composition.objects
        .filter(classe=classe, annee=annee, numero=numero)
        .select_related('matiere')
    )
    index_compos = {(c.eleve_id, c.matiere_id): c for c in toutes_compos}
    inscriptions = (
        classe.inscriptions
        .filter(is_active=True)
        .select_related('eleve')
        .only('eleve__id')
    )
    moyennes = []
    for insc in inscriptions:
        eleve_pk = insc.eleve_id
        total_coeffic = Decimal('0')
        total_coef = 0
        for mat in matieres:
            if mat.is_conduite:
                continue
            compo = index_compos.get((eleve_pk, mat.pk))
            if compo and compo.note is not None and compo.note_max:
                note_sur_10 = (Decimal(str(compo.note)) / Decimal(str(compo.note_max))) * Decimal('10')
                total_coeffic += note_sur_10.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                total_coef += 1
        if total_coef > 0:
            moy_gen = float(
                (total_coeffic / Decimal(str(total_coef))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            )
            moyennes.append((eleve_pk, moy_gen))
    return _attribuer_rangs_ex_aequo(moyennes)
