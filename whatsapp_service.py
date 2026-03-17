import http.client
import json

class WhatsAppService:
    def __init__(self, config):
        self.config = config

    def _enviar(self, payload):
        token = self.config.get('WA_TOKEN')
        phone_id = self.config.get('WA_PHONE_NUMBER_ID')
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
        
        conn = http.client.HTTPSConnection("graph.facebook.com")
        try:
            conn.request("POST", f"/v20.0/{phone_id}/messages", json.dumps(payload), headers)
            res = conn.getresponse()
            return res.status
        except:
            return 500
        finally:
            conn.close()

    def enviar_texto(self, to, text):
        return self._enviar({"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text}})

    def enviar_botones(self, to, text, buttons):
        return self._enviar({
            "messaging_product": "whatsapp", "to": to, "type": "interactive",
            "interactive": {
                "type": "button", "body": {"text": text},
                "action": {"buttons": [{"type": "reply", "reply": b} for b in buttons]}
            }
        })

    def enviar_lista(self, to, header, body, footer, button_text, sections):
        return self._enviar({
            "messaging_product": "whatsapp", "to": to, "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {"type": "text", "text": header},
                "body": {"text": body},
                "footer": {"text": footer},
                "action": {"button": button_text, "sections": sections}
            }
        })