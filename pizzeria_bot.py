from whatsapp_service import WhatsAppService
from models import db, Cliente, Pedido
import json

class PizzeriaBot:
    """Lógica de negocio y gestión de estados del bot."""
    
    def __init__(self, config):
        # Pasamos la configuración al servicio dependiente
        self.wa = WhatsAppService(config)

    def procesar_mensaje_entrante(self, to_number, text_input, interactive_input=None):
        """Normaliza el número y decide la respuesta."""
        wa_id = to_number
        
        # --- NORMALIZACIÓN PARA MÉXICO (Fix Error #131030) ---
        if wa_id.startswith("521") and len(wa_id) == 13:
            wa_id = "52" + wa_id[3:]
            print(f"DEBUG: Número normalizado -> {wa_id}", flush=True)

        text_input = text_input.lower().strip()

        # Lógica de respuesta básica (escalable a estados después)
        if "hola" in text_input:
            respuesta = "🍕 ¡Hola! Bienvenido a Pizzería Mesa Code. ¿Qué deseas ordenar?"
            return self.wa.enviar_texto(wa_id, respuesta)
        
        return self.wa.enviar_texto(wa_id, "🤖 Menú: Escribe 'Hola' para comenzar.")