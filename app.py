import os
from flask import Flask, request, jsonify, render_template
from config import Config
from models import db
from pizzeria_bot import PizzeriaBot

# 1. Crear la instancia de Flask
app = Flask(__name__)
app.config.from_object(Config)

# 2. Inicializar la base de datos con la app
db.init_app(app)

# 3. Instanciar el bot pasando app.config explícitamente
# Esto soluciona el RuntimeError: Working outside of application context
bot = PizzeriaBot(app.config)

# Crear tablas (en SQLite o PostgreSQL)
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    # Dashboard para ver pedidos
    from models import Pedido
    registros = Pedido.query.order_by(Pedido.fecha_pedido.desc()).all()
    return render_template('index.html', registros=registros)

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        # Validación de Meta
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if challenge and token == app.config['WEBHOOK_VERIFY_TOKEN']:
            return challenge, 200
        return "Error de validación", 401
    
    elif request.method == 'POST':
        data = request.get_json()
        
        # Validación de estructura de mensaje
        try:
            val = data['entry'][0]['changes'][0]['value']
            if 'messages' in val:
                msg = val['messages'][0]
                num = msg['from']
                
                text = msg.get('text', {}).get('body', '')
                inter = msg.get('interactive', {}).get(msg.get('interactive', {}).get('type', ''), {}).get('id')
                
                # Ejecutar lógica del bot
                bot.procesar_mensaje_entrante(num, text, inter)
                
            return jsonify({"status": "ok"}), 200
        except Exception as e:
            print(f"DEBUG ERROR WEBHOOK: {e}", flush=True)
            return jsonify({"status": "error"}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=True)