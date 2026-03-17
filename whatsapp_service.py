# ~/Documents/APIMETAPYTHON/whatsapp_service.py
import http.client
import json

class WhatsAppService:
    def __init__(self, config):
        self.config = config

    def _enviar(self, payload):
        """Ejecuta la petición POST a Meta con manejo de errores."""
        token = self.config.get('WA_TOKEN')
        phone_id = self.config.get('WA_PHONE_NUMBER_ID')
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        
        conn = http.client.HTTPSConnection("graph.facebook.com")
        try:
            # Usamos la versión v20.0 o v19.0
            conn.request("POST", f"/v20.0/{phone_id}/messages", json.dumps(payload), headers)
            res = conn.getresponse()
            data_res = res.read().decode()
            print(f"DEBUG API: {res.status} {data_res}", flush=True)
            return res.status
        except Exception as e:
            print(f"ERROR SISTEMA: {e}", flush=True)
            return 500
        finally:
            conn.close()

    def enviar_texto(self, to, text):
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text}
        }
        return self._enviar(payload)

    def enviar_botones(self, to, text, buttons):
        """Envía botones de respuesta rápida."""
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": text},
                "action": {
                    "buttons": [{"type": "reply", "reply": b} for b in buttons]
                }
            }
        }
        return self._enviar(payload)

    def enviar_lista(self, to, header, body, footer, button_text, sections):
        """
        Envía una lista de opciones. 
        CORRECCIÓN: El footer NO lleva el campo 'type'.
        """
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {"type": "text", "text": header},
                "body": {"text": body},
                "footer": {"text": footer},  # <--- Corregido aquí
                "action": {
                    "button": button_text,
                    "sections": sections
                }
            }
        }
        return self._enviar(payload)