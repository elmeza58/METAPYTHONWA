import os
import json
import http.client
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)

# --- CONFIGURACION DE PERSISTENCIA ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///metapython.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Modelo de Base de Datos
class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha_y_hora = db.Column(db.DateTime, default=datetime.utcnow)
    texto = db.Column(db.TEXT)

with app.app_context():
    db.create_all()

# --- LÓGICA DEL WEBHOOK ---

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        # Validacion requerida por Meta para activar el webhook
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if challenge and token == 'ANDERCODE':
            return challenge, 200
        return "Token inválido", 401
    
    elif request.method == 'POST':
        data = request.get_json()
        # Flush=True asegura que el log aparezca al instante en Render
        print(f"DEBUG: JSON recibido -> {json.dumps(data)}", flush=True)

        try:
            # Navegacion segura en el JSON anidado de Meta
            entry = data['entry'][0]
            changes = entry['changes'][0]
            value = changes ['value']

            if 'messages' in value:
                message_obj = value['messages'][0]
                wa_id = message_obj['from']

                # Guardamos en la BS para auditoría
                nuevo_log = Log(texto=json.dumps(message_obj))
                db.session.add(nuevo_log)
                db.session.commit()

                # Procesamos solo si es texto o interactivo
                if 'text' in message_obj:
                    msg_text = message_obj['text']['body']
                    procesar_respuesta(msg_text, wa_id)
                elif 'interactive' in message_obj:
                    # Caso para botones o listas
                    tipo_i = message_obj['interactive']['type']
                    msg_text = message_obj[tipo_i]['id']
                    procesar_respuesta(msg_text, wa_id)
            
            return jsonify({"status": "ok"}), 200
        except Exception as e:
            print(f"ERROR: {str(e)}", flush=True)
            return jsonify({"status": "error"}), 200
        
def procesar_respuesta(texto, numero):
    """Lógica de decisióon el Bot"""
    texto = texto.lower().strip()

    if "hola" in texto:
        respuesta = "🚀 ¡Hola! Bienvenido al bot de prueba en macOS."
    elif "1" in texto:
        respuesta = "Has seleccionado la opcion 1: Informacion técnica."
    else:
        respuesta = "🤖 Menú:\n1. Informacion\n2. Ubicación\nEnvía 'Hola' para empezar."

    enviar_a_whatsapp(respuesta, numero)

def enviar_a_whatsapp(cuerpo, numero):
    """Llamada a la Graph API de Meta"""
    # Importante: Reemplazar con tus credenciales reales
    token_temporal = "EAAKzjv2Ge8YBQ0bClXztv7qjaCgAZCuwh0hJypslp1BAZAk4FA0bkSlS3UeJs9srijOmUMXrH3lh6J7tcikYF6bZAlinDHXxhNTDXCpq6DGedfRdp7hqJFxdrk0Xd7F4dQW5AhLMcdA1eBjHMXW6WFm8q2AOZBo88p3ACm97Spd4NMSNAvxZByRE25E2TJ5dGnpTjs4Qn3he2pBgddAd1qZBJaNksR5xTHZBdRIs4z3eqy4XRwGXrbbkEBNnyvuspW3tRxWytqNwv0tgOA8i9yx4AZDZD"
    phone_id = "1077626325424911"

    payload = json.dumps({
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": numero,
        "type": "text",
        "text": {"body": cuerpo}
    })

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token_temporal}"
    }

    conn = http.client.HTTPSConnection("graph.facebook.com")
    try:
        # Usamos v19.0 que es la mas estable para bots educativos
        conn.request("POST", f"/v19.0/{phone_id}/messages", payload, headers)
        res = conn.getresponse()
        data_res = res.read().decode()
        print(f"DEBUG: Respuesta Meta -> {res.status} {data_res}", flush=True)
    except Exception as e:
        print(f"ERROR DE CONEXIÓN: {e}", flush=True)
    finally:
        conn.close()

@app.route('/')
def index():
    """Vista simple para ver si el servidor vive"""
    registros = Log.query.order_by(Log.fecha_y_hora.desc()).all()
    return render_template('index.html', registros=registros)

if __name__ == '__main__':
    # Render usa el puert dinámico asignado en la variable PORT
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=True)

