import os
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from django.conf import settings
from django.utils.html import strip_tags

def generer_bulletin_pdf(response, eleve, periode, annee, etab, inscription, lignes, moy_generale, total_coeffic, total_coef, rang, effectif, appre_directeur, modele=None):
    """Génère le bulletin en PDF avec ReportLab."""
    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=1.5*cm, leftMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm
    )
    elements = []
    styles = getSampleStyleSheet()
    
    # Styles personnalisés
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=colors.HexColor('#1565C0'),
        alignment=1, # Center
        spaceAfter=10
    )
    
    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        alignment=1,
        spaceAfter=20
    )
    
    info_style = ParagraphStyle(
        'InfoStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14
    )
    
    # 1. Logo
    afficher_logo = True
    if modele and hasattr(modele, 'afficher_logo') and not modele.afficher_logo:
        afficher_logo = False
        
    if afficher_logo and etab.logo and hasattr(etab.logo, 'path'):
        try:
            if os.path.exists(etab.logo.path):
                logo_img = Image(etab.logo.path, width=2.5*cm, height=2.5*cm)
                logo_img.hAlign = 'CENTER'
                elements.append(logo_img)
                elements.append(Spacer(1, 0.3*cm))
        except Exception:
            pass
            
    # 2. En-tête de l'école
    if modele and modele.entete_personnalise:
        entete_brut = modele.entete_personnalise
        entete_brut = entete_brut.replace('[NOM_ELEVE]', f"{eleve.nom} {eleve.prenom}")
        entete_brut = entete_brut.replace('[CLASSE]', inscription.classe.nom if inscription else '')
        entete_brut = entete_brut.replace('[MATRICULE]', eleve.matricule or '')
        entete_brut = entete_brut.replace('[ANNEE_SCOLAIRE]', annee.libelle if annee else '')
        entete_brut = entete_brut.replace('[NOM_ECOLE]', etab.nom)
        # Remplacer les balises bloc par des sauts de ligne pour ReportLab
        entete_brut = entete_brut.replace('</p>', '\n').replace('<br>', '\n').replace('<br/>', '\n').replace('</div>', '\n')
        texte_propre = strip_tags(entete_brut)
        for ligne in texte_propre.split('\n'):
            if ligne.strip():
                elements.append(Paragraph(ligne.strip(), subtitle_style))
    else:
        # Nom de l'établissement
        elements.append(Paragraph(etab.nom.upper(), title_style))
        try:
            if etab.parametres.adresse:
                elements.append(Paragraph(etab.parametres.adresse, subtitle_style))
        except:
            pass
        
    elements.append(Spacer(1, 0.5*cm))
    
    # Titre du bulletin
    titre_bulletin = f"BULLETIN DE NOTES — {periode.libelle.upper()} — {annee.libelle if annee else ''}"
    elements.append(Paragraph(titre_bulletin, subtitle_style))
    elements.append(Spacer(1, 0.5*cm))
    
    # 2. Informations de l'élève
    data_info = [
        [
            Paragraph(f"<b>Élève :</b> {eleve.nom} {eleve.prenom}", info_style),
            Paragraph(f"<b>Classe :</b> {inscription.classe.nom if inscription else '—'}", info_style)
        ],
        [
            Paragraph(f"<b>Matricule :</b> {eleve.matricule}", info_style),
            Paragraph(f"<b>Effectif de la classe :</b> {effectif}", info_style)
        ]
    ]
    t_info = Table(data_info, colWidths=[10*cm, 8*cm])
    t_info.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(t_info)
    elements.append(Spacer(1, 0.5*cm))
    
    # 3. Tableau des notes
    headers = ["Matières", "Moy.\nClasse (/20)", "Moy.\nCompo (/40)", "Moy.\nFinale (/20)", "Coef", "Moy x Coef", "Appréciations"]
    data_notes = [headers]
    
    for ligne in lignes:
        matiere = ligne['matiere'].nom[:20] # Truncate if too long
        moy_c = f"{ligne['moy_classe']:.2f}" if ligne['moy_classe'] is not None else "-"
        moy_cmp = f"{ligne['moy_compo']:.2f}" if ligne['moy_compo'] is not None else "-"
        moy_f = f"{ligne['moyenne_finale']:.2f}" if ligne.get('moyenne_finale') is not None else "-"
        coef = str(ligne.get('coef', ligne.get('coefficient', ligne.get('matiere').coefficient if ligne.get('matiere') else '')))
        coeffic = f"{ligne['moy_coeffic']:.2f}" if ligne.get('moy_coeffic') is not None else "-"
        appre = ligne.get('appre', ligne.get('appreciation', ''))
        
        data_notes.append([matiere, moy_c, moy_cmp, moy_f, coef, coeffic, appre])
        
    t_notes = Table(data_notes, colWidths=[4.5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 1.5*cm, 2*cm, 3*cm])
    t_notes.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#E3E8EF')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#1A237E')),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 10),
        
        ('ALIGN', (1,1), (-2,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#B0BEC5')),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F8FAFC')])
    ]))
    elements.append(t_notes)
    elements.append(Spacer(1, 0.5*cm))
    
    # 4. Tableau Récapitulatif (Moyenne, Rang)
    data_recap = [
        ["TOTAL MOY X COEF", f"{total_coeffic:.2f}" if total_coeffic else "-", "MOYENNE GÉNÉRALE", f"{moy_generale:.2f}/20" if moy_generale else "-"],
        ["TOTAL COEFF.", str(total_coef) if total_coef else "-", "RANG DANS LA CLASSE", f"{rang} / {effectif}" if rang else "-"],
        ["APPRÉCIATION DIRECTEUR", appre_directeur, "MOYENNE DU PREMIER", f"{moy_premier:.2f}/20" if 'moy_premier' in locals() and moy_premier else "-"]
    ]
    # Handle moy_premier if missing gracefully
    try:
        from django.db.models import Sum # just to avoid import errors if needed elsewhere
        mp = f"{moy_premier:.2f}/20" if moy_premier else "-"
    except:
        mp = "-"
    data_recap[2][3] = mp
    
    t_recap = Table(data_recap, colWidths=[5*cm, 3.5*cm, 6*cm, 3.5*cm])
    t_recap.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#E3E8EF')),
        ('BACKGROUND', (2,0), (2,-1), colors.HexColor('#E3E8EF')),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#B0BEC5')),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t_recap)
    elements.append(Spacer(1, 1.5*cm))
    
    # 5. Signatures
    data_sign = [
        ["Le Titulaire", "Le Directeur / La Directrice"]
    ]
    t_sign = Table(data_sign, colWidths=[9*cm, 9*cm])
    t_sign.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    elements.append(t_sign)
    
    # 6. Pied de page personnalisé
    if modele and modele.pied_personnalise:
        elements.append(Spacer(1, 1*cm))
        pied_brut = modele.pied_personnalise
        pied_brut = pied_brut.replace('[NOM_ELEVE]', f"{eleve.nom} {eleve.prenom}")
        pied_brut = pied_brut.replace('[CLASSE]', inscription.classe.nom if inscription else '')
        pied_brut = pied_brut.replace('[MATRICULE]', eleve.matricule or '')
        pied_brut = pied_brut.replace('[ANNEE_SCOLAIRE]', annee.libelle if annee else '')
        pied_brut = pied_brut.replace('[NOM_ECOLE]', etab.nom)
        pied_brut = pied_brut.replace('</p>', '\n').replace('<br>', '\n').replace('<br/>', '\n').replace('</div>', '\n')
        texte_pied_propre = strip_tags(pied_brut)
        for ligne in texte_pied_propre.split('\n'):
            if ligne.strip():
                elements.append(Paragraph(f"<i>{ligne.strip()}</i>", info_style))
    else:
        try:
            if etab.parametres.pied_bulletin:
                elements.append(Spacer(1, 1*cm))
                elements.append(Paragraph(f"<i>{etab.parametres.pied_bulletin}</i>", info_style))
        except:
            pass
    
    # Génération
    doc.build(elements)
