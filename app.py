import os
from flask import Flask, request, jsonify, render_template
from config import Config
from models import db
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
    from models import Pedido
    return render_template('index.html', registros=Pedido.query.order_by(Pedido.fecha.desc()).all())

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
            msg = val['messages'][0]
            num = msg['from']
            
            text_input = ""
            inter_id = None
            
            if 'text' in msg:
                text_input = msg['text']['body']
            elif 'interactive' in msg:
                type_i = msg['interactive']['type']
                inter_id = msg['interactive'][type_i]['id']
                text_input = msg['interactive'][type_i].get('title', "")

            bot.gestionar_mensaje(num, text_input, inter_id)
        return "OK", 200
    except:
        return "Error", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))