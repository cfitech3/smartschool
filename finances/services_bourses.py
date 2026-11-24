"""
Services métier : Bourses, Réductions & Échéanciers personnalisés par élève.

Principe : le tarif standard (TypeFrais.montant_defaut) n'est jamais modifié.
Le "net à payer" d'un élève sur un frais = tarif standard - réduction accordée.
Les échéances non encore payées sont recalculées pour refléter ce net.
"""
import datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import Echeance, Paiement, ReductionFrais


def get_reduction(eleve, annee, type_frais):
    return ReductionFrais.objects.filter(eleve=eleve, annee=annee, type_frais=type_frais).first()


def net_a_payer(eleve, annee, type_frais):
    """Montant net exigé de l'élève sur ce frais (après bourse/réduction)."""
    base = Decimal(str(type_frais.montant_defaut or 0))
    red = get_reduction(eleve, annee, type_frais)
    reduc = Decimal(str(red.montant)) if red else Decimal('0')
    return max(Decimal('0'), base - reduc)


def _statut_ouvert(date_limite, today):
    return 'retard' if (date_limite and date_limite < today) else 'a_payer'


def _consolider_acompte_non_affecte(eleve, annee, type_frais):
    """
    Si l'élève a versé en caisse un acompte partiel valide supérieur à la somme
    des tranches déjà marquées 'payee', matérialise cet acompte sous forme de
    tranche 'payee' (et réduit d'autant les tranches ouvertes) afin que le reste
    à répartir reflète toujours fidèlement les encaissements réels.
    """
    echeances = list(
        Echeance.objects.select_for_update()
        .filter(eleve=eleve, annee=annee, type_frais=type_frais)
        .order_by('numero')
    )
    if not echeances:
        return
    paye_caisse = (
        Paiement.objects.filter(
            eleve=eleve, annee=annee, type_frais=type_frais, statut='valide'
        ).aggregate(t=Sum('montant'))['t']
        or Decimal('0')
    )
    paye_tranches = sum((Decimal(str(e.montant)) for e in echeances if e.statut == 'payee'), Decimal('0'))
    acompte = paye_caisse - paye_tranches
    if acompte <= 0:
        return

    ouvertes = [e for e in echeances if e.statut != 'payee']
    if not ouvertes:
        return

    dernier_paiement = (
        Paiement.objects.filter(
            eleve=eleve, annee=annee, type_frais=type_frais, statut='valide'
        ).order_by('-date_paiement', '-pk').first()
    )
    if not dernier_paiement:
        return

    # Si l'acompte couvre déjà une ou plusieurs tranches ouvertes existantes, les marquer payées d'abord
    for ech in list(ouvertes):
        m_ech = Decimal(str(ech.montant))
        if m_ech > 0 and acompte >= m_ech:
            ech.marquer_payee(dernier_paiement)
            acompte -= m_ech
            ouvertes.remove(ech)

    if acompte <= 0 or not ouvertes:
        return

    # Sinon, scinder la première tranche ouverte en (acompte payé) + (solde ouvert)
    premiere = ouvertes[0]
    solde_premiere = max(Decimal('0'), Decimal(str(premiere.montant)) - acompte)
    # Décaler les numéros suivants pour insérer le solde juste après l'acompte
    for e in reversed(echeances):
        if e.numero > premiere.numero:
            e.numero += 1
            e.save(update_fields=['numero'])

    premiere.libelle = f"{premiere.libelle} (Acompte)"[:50]
    premiere.montant = acompte
    premiere.marquer_payee(dernier_paiement)

    today = timezone.now().date()
    Echeance.objects.create(
        etablissement=eleve.etablissement,
        eleve=eleve,
        annee=annee,
        type_frais=type_frais,
        numero=premiere.numero + 1,
        libelle=f"Solde Tranche {premiere.numero}"[:50],
        montant=solde_premiere,
        date_limite=premiere.date_limite,
        statut='dispensee' if solde_premiere == 0 else _statut_ouvert(premiere.date_limite, today),
    )


def resume_echeancier(eleve, annee, type_frais):
    """Retourne (echeances, total_paye_effectif, reste_a_repartir, net)."""
    echeances = list(Echeance.objects.filter(
        eleve=eleve, annee=annee, type_frais=type_frais
    ).order_by('numero'))
    net = net_a_payer(eleve, annee, type_frais)
    paye_tranches = sum((Decimal(str(e.montant)) for e in echeances if e.statut == 'payee'), Decimal('0'))
    paye_caisse = (
        Paiement.objects.filter(
            eleve=eleve, annee=annee, type_frais=type_frais, statut='valide'
        ).aggregate(t=Sum('montant'))['t']
        or Decimal('0')
    )
    paye = max(paye_tranches, paye_caisse)
    reste = max(Decimal('0'), net - paye)
    return echeances, paye, reste, net


@transaction.atomic
def recalculer_echeances_eleve(eleve, annee, type_frais):
    """
    Réajuste les échéances NON payées d'un élève après octroi / modification /
    suppression d'une bourse. Consolide d'abord tout acompte partiel encaissé.
    """
    _consolider_acompte_non_affecte(eleve, annee, type_frais)
    echeances, _paye, reste, _net = resume_echeancier(eleve, annee, type_frais)
    ouvertes = [e for e in echeances if e.statut != 'payee']
    if not ouvertes:
        return 0

    today = timezone.now().date()
    reste_int = int(reste)

    if reste_int <= 0:
        for e in ouvertes:
            e.montant = 0
            e.statut = 'dispensee'
            e.save(update_fields=['montant', 'statut'])
        return len(ouvertes)

    poids = [int(e.montant) for e in ouvertes]
    total_poids = sum(poids)
    if total_poids <= 0:
        poids = [1] * len(ouvertes)
        total_poids = len(ouvertes)

    nouveaux = [reste_int * p // total_poids for p in poids]
    nouveaux[-1] = reste_int - sum(nouveaux[:-1])

    for e, m in zip(ouvertes, nouveaux):
        e.montant = m
        e.statut = 'dispensee' if m <= 0 else _statut_ouvert(e.date_limite, today)
        e.save(update_fields=['montant', 'statut'])
    return len(ouvertes)


@transaction.atomic
def appliquer_echeancier_personnalise(etab, eleve, annee, type_frais, lignes):
    """
    Remplace les échéances non payées par un échéancier sur mesure.

    `lignes` : liste de dicts {'libelle', 'montant' (int), 'date_limite' (date|None)}.
    La somme des montants doit être égale au reste net à payer.
    Lève ValueError en cas d'incohérence.
    """
    _consolider_acompte_non_affecte(eleve, annee, type_frais)
    echeances, _paye, reste, _net = resume_echeancier(eleve, annee, type_frais)
    reste_int = int(reste)

    if not lignes:
        raise ValueError("Au moins une tranche est requise.")
    for i, l in enumerate(lignes, 1):
        if l['montant'] < 0:
            raise ValueError(f"Montant négatif pour la tranche {i}.")
    total = sum(l['montant'] for l in lignes)
    if total != reste_int:
        raise ValueError(
            f"La somme des tranches ({total:,} FCFA) doit être égale au reste net à payer "
            f"({reste_int:,} FCFA).".replace(',', ' ')
        )

    payees = [e for e in echeances if e.statut == 'payee']
    Echeance.objects.filter(
        eleve=eleve, annee=annee, type_frais=type_frais
    ).exclude(statut='payee').delete()

    today = timezone.now().date()
    numero = max((e.numero for e in payees), default=0)
    crees = []
    for l in lignes:
        numero += 1
        crees.append(Echeance.objects.create(
            etablissement=etab, eleve=eleve, annee=annee, type_frais=type_frais,
            numero=numero,
            libelle=(l.get('libelle') or f"Tranche {numero}")[:50],
            montant=l['montant'],
            date_limite=l.get('date_limite'),
            statut='dispensee' if l['montant'] == 0 else _statut_ouvert(l.get('date_limite'), today),
        ))
    return crees


def detecter_fratrie(eleve, annee):
    """Frères et sœurs (même tuteur) inscrits activement la même année."""
    from eleves.models import Eleve
    if not eleve.tuteur_id or not annee:
        return Eleve.objects.none()
    return Eleve.objects.filter(
        tuteur_id=eleve.tuteur_id,
        etablissement_id=eleve.etablissement_id,
        inscriptions__annee=annee,
        inscriptions__is_active=True,
    ).exclude(pk=eleve.pk).distinct().order_by('date_naissance', 'nom')


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"Date invalide : {value}")
