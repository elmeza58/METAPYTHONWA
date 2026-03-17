import http.client
import json

class WhatsAppService:
    """Servicio modular para comunicación con Meta API."""
    
    def __init__(self, config):
        # Inyectamos la configuración directamente para evitar errores de contexto
        self.config = config
        
    def _enviar_peticion(self, payload):
        """Ejecuta el POST hacia la Graph API de Meta."""
        token = self.config.get('WA_TOKEN')
        phone_id = self.config.get('WA_PHONE_NUMBER_ID')
        
        # Validación de seguridad: Si no hay token, no intentamos el envío
        if not token:
            print("ERROR: No se encontró WHATSAPP_TOKEN en la configuración.", flush=True)
            return None

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        
        url_path = f"/v19.0/{phone_id}/messages"
        conn = http.client.HTTPSConnection("graph.facebook.com")
        
        try:
            conn.request("POST", url_path, json.dumps(payload), headers)
            response = conn.getresponse()
            data = response.read().decode()
            print(f"DEBUG: WhatsApp API {response.status} - {data}", flush=True)
            return response.status
        except Exception as e:
            print(f"ERROR DE CONEXIÓN API: {e}", flush=True)
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