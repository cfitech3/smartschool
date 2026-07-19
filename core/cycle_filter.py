"""
Filtrage global par cycles actifs.
Toutes les requêtes passent par ce helper pour n'afficher
que les données des cycles activés dans l'établissement.
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


def get_classes_actives(etab, annee=None) -> QuerySet:
    """Retourne uniquement les classes des cycles actifs."""
    cycles_ids = get_cycles_actifs_ids(etab)
    qs = Classe.objects.filter(
        etablissement=etab,
        niveau__cycle__in=cycles_ids
    ).select_related('niveau', 'niveau__cycle')
    if annee:
        qs = qs.filter(annee=annee)
    return qs


def get_eleves_actifs(etab, annee=None) -> QuerySet:
    """
    Retourne les élèves réellement scolarisés dans l'établissement.

    Avec annee (recommandé) :
      → Élèves avec une inscription active dans cette année scolaire.
      → C'est la définition la plus précise : correspond aux élèves
        physiquement présents dans l'école cette année.

    Sans annee (fallback) :
      → Élèves avec une inscription dans les cycles actifs.
      → Utilisé quand l'année active n'est pas encore configurée.

    Toujours : Eleve.is_active=True (élève non radié).
    """
    qs = Eleve.objects.filter(etablissement=etab, is_active=True)
    if annee:
        return qs.filter(
            inscriptions__annee=annee,
            inscriptions__is_active=True,
        ).distinct()
    else:
        cycles_ids = get_cycles_actifs_ids(etab)
        return qs.filter(
            inscriptions__classe__niveau__cycle__in=cycles_ids,
            inscriptions__is_active=True,
        ).distinct()


def get_inscriptions_actives(etab, annee=None) -> QuerySet:
    """Retourne uniquement les inscriptions des cycles actifs."""
    cycles_ids = get_cycles_actifs_ids(etab)
    qs = Inscription.objects.filter(
        classe__etablissement=etab,
        classe__niveau__cycle__in=cycles_ids,
        is_active=True,
    )
    if annee:
        qs = qs.filter(annee=annee)
    return qs
