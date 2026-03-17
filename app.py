from flask import Flask, request, jsonify, render_template
import os
import json
from config import Config
from models import db, Cliente, Pedido
from pizzeria_bot import PizzeriaBot

# --- INICIALIZACIÓN DE LA APLICACIÓN ---
app = Flask(__name__)
# Cargar configuraciones profesionales desde config.py
app.config.from_object(Config)

# Inicializar Base de Datos
db.init_app(app)

# Instanciar el cerebro del bot
bot = PizzeriaBot()

# Crear tablas automáticamente al inicio
with app.app_context():
    db.create_all()

# --- RUTAS PRINCIPALES ---

@app.route('/', methods=['GET'])
def index():
    """Dashboard de visualización para ver logs y pedidos."""
    registros = Pedido.query.order_by(Pedido.fecha_pedido.desc()).all()
    # Enviamos los datos al template
    return render_template('index.html', registros=registros)

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    """Punto de enlace para el Webhook de Meta."""
    if request.method == 'GET':
        # Validación del token requerida por Meta
        verify_token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if challenge and verify_token == app.config['WEBHOOK_VERIFY_TOKEN']:
            return challenge, 200
        return jsonify({'error': 'Token de verificación inválido'}), 401
    
    elif request.method == 'POST':
        data = request.get_json()
        print(f"LOG: Payload recibido -> {json.dumps(data)}", flush=True)

        try:
            # Navegación en el JSON anidado de WhatsApp
            entry = data['entry'][0]
            changes = entry['changes'][0]
            value = changes['value']

            # Ignorar notificaciones que no sean de mensajes (ej. estados de leído)
            if 'messages' in value:
                message_obj = value['messages'][0]
                to_number = message_obj['from'] # Número del remitente

                text_input = ""
                interactive_input = None
                
                # Identificar si es mensaje de texto o interactivo
                if 'text' in message_obj:
                    text_input = message_obj['text']['body']
                elif 'interactive' in message_obj:
                    # Capturar la respuesta interactiva (botón o lista)
                    interactive_obj = message_obj['interactive']
                    tipo_i = interactive_obj['type']
                    # El ID del elemento suele ser la clave para la lógica
                    interactive_input = interactive_obj[tipo_i]['id']
                    text_input = interactive_obj[tipo_i]['title']

                # --- LLAMADA AL CEREBRO DEL BOT ---
                if text_input or interactive_input:
                    bot.procesar_mensaje_entrante(to_number, text_input, interactive_input)
            
            # Responder siempre con 200 OK a Meta para evitar bloqueos
            return jsonify({"status": "ok"}), 200
            
        except Exception as e:
            # Captura y log profesional de errores técnicos
            print(f"ERROR: Fallo crítico al procesar webhook -> {str(e)}", flush=True)
            # Responder siempre 200 OK para no bloquear el webhook de Meta
            return jsonify({"status": "error"}), 200

if __name__ == '__main__':
    # Configuración dinámica del puerto para entornos como Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=True)