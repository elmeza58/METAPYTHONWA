import os
import json
from flask import Flask, request, jsonify, render_template
from config import Config
from models import db, Pedido # Importamos Pedido aquí arriba para limpieza
from pizzeria_bot import PizzeriaBot
from whatsapp_service import WhatsAppService

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# Inyección de dependencias
wa_service = WhatsAppService(app.config)
bot = PizzeriaBot(app.config, wa_service)

# Crear tablas si no existen
with app.app_context():
    db.create_all()
    print("✅ Base de datos reseteada y columnas creadas con éxito.")

@app.route('/')
def index():
    # Ordenamos por fecha descendente para ver lo más nuevo arriba
    registros = Pedido.query.order_by(Pedido.fecha.desc()).all()
    return render_template('index.html', registros=registros)

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get('hub.verify_token') == app.config['WEBHOOK_VERIFY_TOKEN']:
            return request.args.get('hub.challenge'), 200
        return "Error de autenticación", 401
    
    data = request.get_json()
    try:
        # Navegación segura en el JSON de Meta
        entry = data['entry'][0]
        changes = entry['changes'][0]
        value = changes['value']
        
        if 'messages' in value:
            msg = value['messages'][0]
            num = msg['from']
            
            text_input = ""
            inter_id = None
            
            # 1. Detectar si es texto normal
            if 'text' in msg:
                text_input = msg['text']['body']
            elif 'interactive' in msg:
                type_i = msg['interactive']['type']
                inter_id = msg['interactive'][type_i]['id']
                # SOLO tomamos el texto si NO es un ID conocido, 
                # pero para estados es mejor priorizar el ID.
                text_input = msg['interactive'][type_i].get('title', "")

            # Log para que veas en Render qué está llegando
            print(f"DEBUG: Input -> Text: {text_input} | ID: {inter_id}", flush=True)
            
            bot.gestionar_mensaje(num, text_input, inter_id)
        
        return "OK", 200
        
    except Exception as e:
        # IMPORTANTE: Esto te dirá el error real en los logs de Render
        print(f"❌ ERROR CRÍTICO EN WEBHOOK: {e}", flush=True)
        return "OK", 200 # Siempre 200 para que Meta no bloquee el webhook

if __name__ == '__main__':
    # Usamos 0.0.0.0 para que Render pueda exponer el servicio
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=True)