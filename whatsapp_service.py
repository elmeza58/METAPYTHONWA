import http.client
import json

class WhatsAppService:
    """
    Servicio encargado de la comunicación técnica con la API de Meta.
    """
    def __init__(self, config):
        # Recibimos la configuración del objeto app.config de Flask
        self.config = config
        
    def _enviar_peticion(self, payload):
        """
        Método privado para ejecutar el POST a los servidores de Facebook.
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config['WA_TOKEN']}"
        }
        
        # Construcción dinámica de la URL con el ID del teléfono
        url_path = f"/v19.0/{self.config['WA_PHONE_NUMBER_ID']}/messages"
        
        conn = http.client.HTTPSConnection("graph.facebook.com")
        try:
            conn.request("POST", url_path, json.dumps(payload), headers)
            response = conn.getresponse()
            data = response.read().decode()
            # Log de depuración para Render
            print(f"DEBUG: WhatsApp API {response.status} - {data}", flush=True)
            return response.status
        except Exception as e:
            print(f"ERROR: Fallo de conexión API WhatsApp -> {e}", flush=True)
            return None
        finally:
            conn.close()

    def enviar_texto(self, to_number, text_body):
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "text",
            "text": {"body": text_body}
        }
        return self._enviar_peticion(payload)

    def enviar_botones(self, to_number, text_body, buttons_list):
        payload = {
            "messaging_product": "whatsapp",
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

    def enviar_lista(self, to_number, header, body, footer, button_text, sections):
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {"type": "text", "text": header},
                "body": {"text": body},
                "footer": {"type": "text", "text": footer},
                "action": {"button": button_text, "sections": sections}
            }
        }
        return self._enviar_peticion(payload)