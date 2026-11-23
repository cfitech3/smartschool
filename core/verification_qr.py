"""
Service de certification et vérification d'authenticité par QR Code signé
pour les bulletins scolaires, relevés universitaires LMD et attestations.

Utilise `django.core.signing` (HMAC-SHA256 avec SECRET_KEY) et le moteur
QR de ReportLab pour générer :
  - un SVG vectoriel inline (pour les vues HTML / impression navigateur)
  - un Drawing ReportLab (pour les bulletins PDF téléchargeables)
  - une page publique `/verifier/<token>/` consultable sans connexion.
"""
import datetime
from django.core import signing
from django.shortcuts import render
from django.urls import reverse
from django.utils.safestring import mark_safe

QR_SALT = 'smartschool-qr-v1'


def generer_token_document(type_doc, eleve, annee=None, periode=None, extra=None):
    """Génère un jeton signé compact représentant un document officiel."""
    payload = {
        't': type_doc,  # 'bulletin' | 'compo' | 'lmd' | 'doc'
        'e': eleve.pk,
        'm': eleve.matricule or '',
        'et': eleve.etablissement_id,
        'a': annee.pk if annee else (periode.annee_id if periode else None),
        'p': periode.pk if periode else None,
        'd': datetime.date.today().isoformat(),
    }
    if extra:
        payload.update(extra)
    return signing.dumps(payload, salt=QR_SALT, compress=True)


def generer_qr_svg(data_url, size=78):
    """
    Génère un QR Code SVG vectoriel autonome (<svg>...</svg>) sans fichier disque.
    """
    try:
        from reportlab.graphics.barcode.qr import QrCodeWidget
        qrw = QrCodeWidget(data_url, barLevel='M')
        qrw.qr.make()
        modules = qrw.qr.modules
        n = len(modules)
        if not n:
            return ''
        margin = 2
        total = n + margin * 2
        paths = []
        for r, row in enumerate(modules):
            y = r + margin
            for c, val in enumerate(row):
                if val:
                    x = c + margin
                    paths.append(f"M{x},{y}h1v1h-1z")
        d_attr = "".join(paths)
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total} {total}" '
            f'width="{size}" height="{size}" shape-rendering="crispEdges" '
            f'role="img" aria-label="QR Code de vérification">'
            f'<rect width="{total}" height="{total}" fill="#ffffff"/>'
            f'<path d="{d_attr}" fill="#0f172a"/>'
            f'</svg>'
        )
        return mark_safe(svg)
    except Exception:
        return ''


def generer_qr_drawing_reportlab(data_url, size_cm=2.4):
    """Retourne un objet Drawing ReportLab contenant le QR Code pour inclusion PDF."""
    try:
        from reportlab.graphics.barcode.qr import QrCodeWidget
        from reportlab.graphics.shapes import Drawing
        from reportlab.lib.units import cm
        dim = size_cm * cm
        qrw = QrCodeWidget(data_url, barLevel='M', barWidth=dim, barHeight=dim)
        d = Drawing(dim, dim)
        d.add(qrw)
        return d
    except Exception:
        return None


def construire_contexte_qr(request, type_doc, eleve, annee=None, periode=None, extra=None):
    """
    Construit le dictionnaire {'qr_token', 'qr_url', 'qr_svg', 'qr_code_court'}
    prêt à être injecté dans le contexte d'un bulletin, relevé LMD ou document.
    """
    token = generer_token_document(type_doc, eleve, annee=annee, periode=periode, extra=extra)
    rel_url = reverse('verifier_document_qr', kwargs={'token': token})
    full_url = request.build_absolute_uri(rel_url) if request else rel_url
    svg = generer_qr_svg(full_url, size=78)
    code_court = token[-10:].upper()
    return {
        'qr_token': token,
        'qr_url': full_url,
        'qr_svg': svg,
        'qr_code_court': code_court,
    }


def verifier_document_qr(request, token):
    """
    Vue publique `/verifier/<token>/` permettant de vérifier l'authenticité
    d'un bulletin, relevé de notes LMD ou certificat en scannant son QR Code.
    """
    from eleves.models import Eleve, Inscription
    from etablissements.models import AnneeScolaire, Etablissement
    from notes.models import Periode, NoteUE

    try:
        data = signing.loads(token, salt=QR_SALT)
    except signing.BadSignature:
        return render(request, 'core/verifier_document.html', {
            'valide': False,
            'erreur': "Signature numérique invalide ou document falsifié.",
        }, status=400)

    type_doc = data.get('t')
    eleve = Eleve.objects.select_related('etablissement').filter(
        pk=data.get('e'), etablissement_id=data.get('et')
    ).first()
    if not eleve:
        return render(request, 'core/verifier_document.html', {
            'valide': False,
            'erreur': "Élève ou établissement introuvable dans la base officielle.",
        }, status=404)

    etab = eleve.etablissement
    periode = Periode.objects.select_related('annee').filter(pk=data.get('p'), etablissement=etab).first() if data.get('p') else None
    annee = periode.annee if periode else (AnneeScolaire.objects.filter(pk=data.get('a'), etablissement=etab).first() if data.get('a') else None)
    insc = Inscription.objects.select_related('classe', 'classe__niveau').filter(
        eleve=eleve, annee=annee
    ).first() or eleve.get_inscription_active()

    details = {
        'type_libelle': 'Document Officiel',
        'periode_libelle': periode.libelle if periode else (annee.libelle if annee else '—'),
        'moyenne_officielle': None,
        'barème': '/20',
        'credits_obtenus': None,
        'credits_requis': None,
        'mention': None,
        'concordance': True,
    }

    if type_doc == 'bulletin' and periode:
        from notes.services import get_matieres_pour_eleve, calculer_bulletin
        classe_m = insc.classe if insc else None
        matieres = get_matieres_pour_eleve(eleve, periode, classe_m)
        _, moy_gen, _, _ = calculer_bulletin(eleve, periode, matieres, classe=classe_m)
        details['type_libelle'] = f"Bulletin de Notes — {periode.libelle}"
        details['moyenne_officielle'] = moy_gen
        details['barème'] = '/20'
        if data.get('moy') is not None and moy_gen is not None:
            details['concordance'] = abs(float(moy_gen) - float(data['moy'])) < 0.05

    elif type_doc == 'compo' and annee:
        from notes.services import get_matieres_pour_eleve, calculer_bulletin_composition
        numero = int(data.get('num') or 1)
        classe_m = insc.classe if insc else None
        matieres = get_matieres_pour_eleve(eleve, annee, classe_m)
        _, moy_gen, _, _ = calculer_bulletin_composition(eleve, annee, numero, matieres)
        details['type_libelle'] = f"Bulletin de Composition N°{numero}"
        details['moyenne_officielle'] = moy_gen
        details['barème'] = '/10'
        if data.get('moy') is not None and moy_gen is not None:
            details['concordance'] = abs(float(moy_gen) - float(data['moy'])) < 0.05

    elif type_doc == 'lmd' and periode:
        notes_ue = NoteUE.objects.filter(eleve=eleve, periode=periode).select_related('ue')
        c_obt = sum(n.ue.credits for n in notes_ue if n.credits_valides)
        c_req = sum(n.ue.credits for n in notes_ue)
        pts = sum(float(n.note_retenue) * n.ue.credits for n in notes_ue if n.note_retenue is not None)
        c_not = sum(n.ue.credits for n in notes_ue if n.note_retenue is not None)
        moy_gen = round(pts / c_not, 2) if c_not > 0 else None
        details['type_libelle'] = f"Relevé de Notes Universitaire (LMD) — {periode.libelle}"
        details['moyenne_officielle'] = moy_gen
        details['credits_obtenus'] = c_obt
        details['credits_requis'] = c_req
        if data.get('moy') is not None and moy_gen is not None:
            details['concordance'] = abs(float(moy_gen) - float(data['moy'])) < 0.05

    elif type_doc == 'doc':
        doc_nom = data.get('doc_type', 'Attestation / Certificat')
        LABELS = {
            'certificat_scolarite': 'Certificat de Scolarité',
            'attestation_frequentation': 'Attestation de Fréquentation',
            'recu_paiement_annuel': 'Récapitulatif Annuel de Paiement',
        }
        details['type_libelle'] = LABELS.get(doc_nom, doc_nom)
        details['ref'] = data.get('ref', '')

    return render(request, 'core/verifier_document.html', {
        'valide': True,
        'etab': etab,
        'eleve': eleve,
        'annee': annee,
        'periode': periode,
        'inscription': insc,
        'date_emission': data.get('d'),
        'details': details,
        'code_court': token[-10:].upper(),
    })

