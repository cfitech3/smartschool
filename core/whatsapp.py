import logging
import urllib.parse
import urllib.request
from django.conf import settings

logger = logging.getLogger(__name__)

def send_whatsapp_message(telephone, message):
    """
    Envoie un message WhatsApp au numéro donné.
    Le comportement dépend de WHATSAPP_API_PROVIDER dans settings.py.
    """
    if not getattr(settings, 'WHATSAPP_ENABLED', False):
        logger.info(f"[WhatsApp Désactivé] Message ignoré pour {telephone}")
        return False

    if not telephone:
        logger.warning("Tentative d'envoi WhatsApp sans numéro de téléphone.")
        return False

    # Nettoyage basique du numéro (retirer les espaces et le +)
    phone_clean = telephone.replace(' ', '').replace('+', '')
    
    provider = getattr(settings, 'WHATSAPP_API_PROVIDER', 'dummy')

    if provider == 'dummy':
        # Mode développement : journalisation compatible avec tous les encodages console (Windows cp1252 inclus)
        logger.info("==================================================")
        logger.info(" [WHATSAPP SIMULE] DESTINATAIRE : %s", phone_clean)
        logger.info("MESSAGE:\n%s", message)
        logger.info("==================================================")
        return True

    elif provider == 'ultramsg':
        # Exemple d'intégration UltraMsg
        url = getattr(settings, 'WHATSAPP_API_URL', '')
        token = getattr(settings, 'WHATSAPP_API_TOKEN', '')
        instance_id = getattr(settings, 'WHATSAPP_INSTANCE_ID', '')
        
        if not url or not token or not instance_id:
            logger.error("Configuration WhatsApp UltraMsg incomplète.")
            return False

        endpoint = f"{url}/{instance_id}/messages/chat"
        payload = {
            "token": token,
            "to": phone_clean,
            "body": message
        }
        try:
            try:
                import requests
                response = requests.post(endpoint, data=payload, timeout=10)
                status_code = response.status_code
                resp_text = response.text
            except ImportError:
                data = urllib.parse.urlencode(payload).encode('utf-8')
                req = urllib.request.Request(endpoint, data=data, method='POST')
                with urllib.request.urlopen(req, timeout=10) as resp:
                    status_code = resp.status
                    resp_text = resp.read().decode('utf-8', errors='replace')

            if status_code == 200:
                logger.info(f"WhatsApp UltraMsg envoyé à {phone_clean}")
                return True
            else:
                logger.error(f"Erreur UltraMsg: {resp_text}")
                return False
        except Exception as e:
            logger.error(f"Erreur connexion UltraMsg: {e}")
            return False

    elif provider == 'twilio':
        # Exemple d'intégration Twilio (nécessite le format whatsapp:+123456789)
        url = getattr(settings, 'WHATSAPP_API_URL', '')
        token = getattr(settings, 'WHATSAPP_API_TOKEN', '')
        # Twilio requiert un POST avec Basic Auth et des params spécifiques form-encoded
        # Ici on log juste car l'implémentation complète requiert souvent la lib twilio
        logger.error("Fournisseur Twilio défini mais non implémenté. Utilisez la lib twilio-python.")
        return False

    else:
        logger.error(f"Fournisseur WhatsApp inconnu: {provider}")
        return False
