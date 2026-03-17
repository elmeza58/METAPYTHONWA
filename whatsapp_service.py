import http.client
import json
from flask import current_app

class WhatsAppService:
    """Servicio para comunicarse con la API de WhatsApp Cloud."""
    
    def __init__(self):
        self.config = current_app.config
        
    def _enviar_peticion(self, payload):
        """Función interna genérica para enviar peticiones POST a la API."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config['WA_TOKEN']}"
        }
        
        url_path = f"/v19.0/{self.config['WA_PHONE_NUMBER_ID']}/messages"
        
        conn = http.client.HTTPSConnection("graph.facebook.com")
        try:
            conn.request("POST", url_path, json.dumps(payload), headers)
            response = conn.getresponse()
            data = response.read().decode()
            print(f"WHATSAPP API RESPONSE: {response.status} {data}")
            return response.status
        except Exception as e:
            print(f"ERROR DE CONEXIÓN CON WHATSAPP: {e}")
            return None
        finally:
            conn.close()

    def enviar_texto(self, to_number, text_body):
        """Envía un mensaje de texto simple."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "text",
            "text": {"body": text_body}
        }
        return self._enviar_peticion(payload)

    def enviar_botones(self, to_number, text_body, buttons_list):
        """Envía un mensaje con botones interactivos (máximo 3)."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": text_body},
                "action": {
                    "buttons": [{"type": "reply", "reply": b} for b in buttons_list]
                }
            }
        }
        return self._enviar_peticion(payload)

    def enviar_lista(self, to_number, header_text, body_text, footer_text, button_text, sections):
        """Envía una lista de mensajes interactiva (menú más complejo)."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {"type": "text", "text": header_text},
                "body": {"text": body_text},
                "footer": {"type": "text", "text": footer_text},
                "action": {
                    "button": button_text,
                    "sections": sections
                }
            }
        }
        return self._enviar_peticion(payload)