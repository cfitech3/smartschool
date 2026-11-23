from html.parser import HTMLParser
import logging
import re
from django import template
from django.utils.safestring import mark_safe
from django.utils.html import escape

register = template.Library()
logger = logging.getLogger(__name__)

_ALLOWED_TAGS = frozenset({
    'p', 'br', 'b', 'strong', 'i', 'em', 'u', 's', 'sub', 'sup',
    'ul', 'ol', 'li', 'span', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'table', 'thead', 'tbody', 'tfoot', 'tr', 'td', 'th',
    'hr', 'blockquote', 'pre', 'code', 'small', 'center', 'a',
})
_VOID_TAGS = frozenset({'br', 'hr'})
_DROP_CONTENT_TAGS = frozenset({
    'script', 'style', 'iframe', 'object', 'embed', 'applet', 'svg', 'math',
})
_ALLOWED_ATTRS = frozenset({
    'class', 'colspan', 'rowspan', 'align', 'valign',
    'width', 'height', 'border', 'cellpadding', 'cellspacing', 'style', 'href',
})
_DANGEROUS_STYLE_RE = re.compile(
    r'(?:expression\s*\(|javascript\s*:|vbscript\s*:|data\s*:|url\s*\(|-moz-binding|@import)',
    re.IGNORECASE,
)


def _is_safe_href(val):
    v = (val or '').strip().lower()
    return v.startswith(('http://', 'https://', 'mailto:', '/')) or v.startswith('#')


class _AllowlistHTMLSanitizer(HTMLParser):
    """Sanitizer HTML par liste blanche stricte (résistant aux contournements regex)."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.out = []
        self._drop_depth = 0
        self._drop_tag_stack = []

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if t in _DROP_CONTENT_TAGS:
            self._drop_depth += 1
            self._drop_tag_stack.append(t)
            return
        if self._drop_depth > 0 or t not in _ALLOWED_TAGS:
            return
        safe_attrs = []
        for k, v in attrs:
            ak = (k or '').lower()
            if ak not in _ALLOWED_ATTRS or ak.startswith('on'):
                continue
            av = v or ''
            if ak == 'style' and _DANGEROUS_STYLE_RE.search(av):
                continue
            if ak == 'href' and not _is_safe_href(av):
                continue
            if ak == 'href' and t != 'a':
                continue
            safe_attrs.append(f' {ak}="{escape(av)}"')
        self.out.append(f'<{t}{"".join(safe_attrs)}>')

    def handle_startendtag(self, tag, attrs):
        t = tag.lower()
        if self._drop_depth > 0 or t in _DROP_CONTENT_TAGS or t not in _ALLOWED_TAGS:
            return
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        t = tag.lower()
        if self._drop_tag_stack and self._drop_tag_stack[-1] == t:
            self._drop_tag_stack.pop()
            self._drop_depth = max(0, self._drop_depth - 1)
            return
        if self._drop_depth > 0 or t not in _ALLOWED_TAGS or t in _VOID_TAGS:
            return
        self.out.append(f'</{t}>')

    def handle_data(self, data):
        if self._drop_depth == 0:
            self.out.append(escape(data))

    def handle_entityref(self, name):
        if self._drop_depth == 0:
            self.out.append(f'&{name};')

    def handle_charref(self, name):
        if self._drop_depth == 0:
            self.out.append(f'&#{name};')


def sanitize_html_fragment(html_text):
    """Nettoie un fragment HTML via une liste blanche stricte de balises et attributs."""
    if not html_text:
        return html_text
    parser = _AllowlistHTMLSanitizer()
    parser.feed(str(html_text))
    parser.close()
    return ''.join(parser.out)

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def render_tags(text, eleve):
    """
    Substitue les balises [TAG] du modèle de document par les données de l'élève.
    Les valeurs dynamiques sont systématiquement échappées (escape) avant insertion
    et le modèle est nettoyé contre toute balise <script> ou attribut on* (anti-XSS stocké).
    """
    if not text or not eleve:
        return text

    text = sanitize_html_fragment(text)

    # Chaque valeur dynamique est échappée individuellement avant substitution
    nom_complet = f"{eleve.nom} {eleve.prenom}"
    text = text.replace('[NOM_ELEVE]', escape(nom_complet))
    text = text.replace('[MATRICULE]', escape(eleve.matricule or ''))

    date_n = eleve.date_naissance.strftime('%d/%m/%Y') if eleve.date_naissance else ''
    text = text.replace('[DATE_NAISSANCE]', escape(date_n))
    text = text.replace('[LIEU_NAISSANCE]', escape(getattr(eleve, 'lieu_naissance', '') or ''))

    try:
        insc = eleve.inscriptions.filter(is_active=True).first()
        if insc:
            text = text.replace('[CLASSE]', escape(insc.classe.nom))
            text = text.replace('[ANNEE_SCOLAIRE]', escape(insc.annee.libelle))
    except Exception:
        logger.warning("Impossible de résoudre l'inscription active pour l'élève %s", getattr(eleve, 'pk', None), exc_info=True)

    try:
        text = text.replace('[NOM_ECOLE]', escape(eleve.etablissement.nom))
    except Exception:
        logger.warning("Impossible de résoudre l'établissement pour l'élève %s", getattr(eleve, 'pk', None), exc_info=True)

    return mark_safe(text)
