import http.client
import json

class WhatsAppService:
    def __init__(self, config):
        # Guardamos el objeto config completo
        self.config = config
        
    def _enviar_peticion(self, payload):
        # Accedemos a la clave WA_TOKEN que definimos en Config
        token = self.config.get('WA_TOKEN')
        phone_id = self.config.get('WA_PHONE_NUMBER_ID')
        
        # Validación de seguridad con print para el log de Render
        if not token or token == "PEGAR_AQUI_TU_TOKEN_LARGO_DE_META":
            print("CRÍTICO: El WHATSAPP_TOKEN sigue sin estar configurado correctamente.", flush=True)
            return None

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        
        conn = http.client.HTTPSConnection("graph.facebook.com")
        try:
            # Usamos v19.0 que es la más estable
            url = f"/v19.0/{phone_id}/messages"
            conn.request("POST", url, json.dumps(payload), headers)
            res = conn.getresponse()
            data = res.read().decode()
            
            print(f"DEBUG: Respuesta Meta API -> {res.status} {data}", flush=True)
            return res.status
        except Exception as e:
            print(f"ERROR DE CONEXIÓN: {e}", flush=True)
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