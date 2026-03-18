import os, json
from flask import Flask, request, render_template
from config import Config
from models import db, Pedido
from pizzeria_bot import PizzeriaBot
from whatsapp_service import WhatsAppService

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

wa_service = WhatsAppService(app.config)
bot = PizzeriaBot(app.config, wa_service)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    pedidos = Pedido.query.order_by(Pedido.fecha.desc()).all()
    registros = []
    for p in pedidos:
        d = json.loads(p.detalles_json)
        pizzas = [f"{pz['nombre']} ({', '.join(pz['ingredientes'])})" for pz in d.get('pizzas', [])]
        registros.append({
            "id": p.id, "fecha": p.fecha, "cliente": p.cliente.nombre or "Cliente WA",
            "telefono": p.cliente.telefono, "total": p.total, "pizzas": pizzas,
            "extras": d.get('extras', []), "direccion": d.get('direccion', 'Recoger')
        })
    return render_template('index.html', registros=registros)

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get('hub.verify_token') == app.config['WEBHOOK_VERIFY_TOKEN']:
            return request.args.get('hub.challenge'), 200
        return "Error", 401
    
    data = request.get_json()
    try:
        val = data['entry'][0]['changes'][0]['value']
        if 'messages' in val:
            msg = val['messages'][0]; num = msg['from']
            text_input = msg.get('text', {}).get('body', '')
            inter_id = None
            if 'interactive' in msg:
                type_i = msg['interactive']['type']
                inter_id = msg['interactive'][type_i]['id']
                text_input = msg['interactive'][type_i].get('title', "")
            
            print(f"DEBUG INCOMING: {num} | {text_input} | {inter_id}", flush=True)
            bot.gestionar_pedido(num, text_input, inter_id)
        return "OK", 200
    except Exception as e:
        print(f"❌ ERROR WEBHOOK: {e}", flush=True)
        return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))