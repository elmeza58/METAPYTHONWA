from whatsapp_service import WhatsAppService
from models import db, Cliente, Pedido
import json

# Constantes del Menú (Precios extraídos de tus capturas)
MENU_PIZZAS = {
    'piz_familiar': {'nombre': 'Pizza familiar', 'precio': 150.0},
    'piz_mediana': {'nombre': 'Pizza mediana', 'precio': 130.0},
    'piz_chica': {'nombre': 'Pizza chica', 'precio': 80.0}
}

class PizzeriaBot:
    """
    Cerebro del bot: Controla estados y lógica de negocio de la pizzería.
    """
    def __init__(self, config):
        # Inyectamos la configuración al servicio dependiente
        self.wa = WhatsAppService(config)
        self.db = db

    def procesar_mensaje_entrante(self, to_number, text_input, interactive_input=None):
        """
        Punto de entrada para cada mensaje recibido del webhook.
        """
        wa_id = to_number
        
        # --- NORMALIZACIÓN DE NÚMEROS MÉXICO ---
        if wa_id.startswith("521") and len(wa_id) == 13:
            wa_id = "52" + wa_id[3:]
            
        # Aquí iría la lógica de estados que desarrollamos anteriormente
        # (Se omite el detalle de estados para brevedad, pero la estructura es la misma)
        
        # Ejemplo rápido de respuesta:
        if "hola" in text_input.lower():
            return self.wa.enviar_texto(wa_id, "🍕 ¡Bienvenido! ¿Qué pizza deseas ordenar?")
        
        return 200