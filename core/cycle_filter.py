"""
Filtrage global par cycles actifs.
Toutes les requêtes passent par ce helper pour n'afficher
que les données des cycles activés dans l'établissement,
et en plus filtrer par les divisions de l'utilisateur connecté.
"""
from etablissements.models import CycleActif, Classe, AnneeScolaire
from eleves.models import Eleve, Inscription
from django.db.models import QuerySet


def get_cycles_actifs_ids(etab) -> list:
    """Retourne la liste des IDs de cycles actifs pour un établissement."""
    return list(
        CycleActif.objects.filter(etablissement=etab, is_active=True)
        .values_list('cycle_id', flat=True)
    )


def get_cycles_actifs_ids_pour_user(etab, user=None) -> list:
    """
    Retourne les IDs de cycles actifs filtrés selon les divisions de l'utilisateur.

    - user None ou sans divisions → tous les cycles actifs (admin global)
    - user avec divisions → uniquement les cycles de ses divisions
    """
    cycles_ids = get_cycles_actifs_ids(etab)
    if user and not getattr(user, 'is_super_admin', False) and not getattr(user, 'is_admin', False):
        # Utilisateurs non-admin (enseignant, surveillant, secrétariat...) :
        # filtrer par divisions si elles sont définies
        divisions = user.divisions.all()
        if divisions.exists():
            division_cycle_ids = set(
                divisions.values_list('cycles__pk', flat=True)
            )
            cycles_ids = [cid for cid in cycles_ids if cid in division_cycle_ids]
    elif user and getattr(user, 'is_admin', False) and not getattr(user, 'is_super_admin', False):
        # Directeur (admin) : filtrer par divisions si assigné à des divisions spécifiques
        divisions = user.divisions.all()
        if divisions.exists():
            division_cycle_ids = set(
                divisions.values_list('cycles__pk', flat=True)
            )
            cycles_ids = [cid for cid in cycles_ids if cid in division_cycle_ids]
        # Si aucune division → directeur global, voit tout
    # super_admin → voit tout, pas de restriction
    return cycles_ids


def get_classes_actives(etab, annee=None, user=None) -> QuerySet:
    """
    Retourne uniquement les classes des cycles actifs, filtrées par divisions de l'utilisateur.

    - user=None ou super_admin → tous les cycles actifs
    - admin avec divisions → seulement les cycles de ses divisions
    - admin sans divisions → tous les cycles actifs (directeur global)
    - enseignant/surveillant avec divisions → seulement ses divisions
    """
    cycles_ids = get_cycles_actifs_ids_pour_user(etab, user)
    qs = Classe.objects.filter(
        etablissement=etab,
        niveau__cycle__in=cycles_ids
    ).select_related('niveau', 'niveau__cycle')
    if annee:
        qs = qs.filter(annee=annee)
    return qs


def get_eleves_actifs(etab, annee=None, user=None) -> QuerySet:
    """
    Retourne les élèves réellement scolarisés dans l'établissement.
    Filtrés par divisions de l'utilisateur si applicable.

    Avec annee (recommandé) :
      → Élèves avec une inscription active dans cette année scolaire.

    Sans annee (fallback) :
      → Élèves avec une inscription dans les cycles actifs.

    Toujours : Eleve.is_active=True (élève non radié).
    """
    qs = Eleve.objects.filter(etablissement=etab, is_active=True)
    if annee:
        return qs.filter(
            inscriptions__annee=annee,
            inscriptions__is_active=True,
        ).distinct()
    else:
        cycles_ids = get_cycles_actifs_ids_pour_user(etab, user)
        return qs.filter(
            inscriptions__classe__niveau__cycle__in=cycles_ids,
            inscriptions__is_active=True,
        ).distinct()


def get_inscriptions_actives(etab, annee=None, user=None) -> QuerySet:
    """Retourne uniquement les inscriptions des cycles actifs de l'utilisateur."""
    cycles_ids = get_cycles_actifs_ids_pour_user(etab, user)
    qs = Inscription.objects.filter(
        classe__etablissement=etab,
        classe__niveau__cycle__in=cycles_ids,
        is_active=True,
    )
    if annee:
        qs = qs.filter(annee=annee)
    return qs
