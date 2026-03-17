import os
from flask import Flask, request, jsonify, render_template
from config import Config
from models import db
from pizzeria_bot import PizzeriaBot

# 1. Configuración de la App
app = Flask(__name__)
app.config.from_object(Config)

# 2. Inicialización de DB
db.init_app(app)

# 3. Instanciar Bot pasando app.config explícitamente (SOLUCIONA RUNTIMERROR)
bot = PizzeriaBot(app.config)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    # Vista del Dashboard
    from models import Pedido
    pedidos = Pedido.query.order_by(Pedido.fecha_pedido.desc()).all()
    return render_template('index.html', registros=pedidos)

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if challenge and token == app.config['WEBHOOK_VERIFY_TOKEN']:
            return challenge, 200
        return "Token inválido", 401
    
    elif request.method == 'POST':
        data = request.get_json()
        try:
            val = data['entry'][0]['changes'][0]['value']
            if 'messages' in val:
                msg = val['messages'][0]
                num = msg['from']
                text = msg.get('text', {}).get('body', '')
                
                # Ejecutar bot
                bot.procesar_mensaje_entrante(num, text)
                
            return jsonify({"status": "ok"}), 200
        except Exception as e:
            print(f"DEBUG WEBHOOK ERROR: {e}", flush=True)
            return jsonify({"status": "error"}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=True)