import os
import json
import http.client
from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy

# --- INICIALIZACIÓN DE LA APLICACIÓN ---
app = Flask(__name__)

# Configuración de persistencia (SQLite)
# Nota: La base de datos es efímera en Render (capa gratuita).
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///metapython.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODELO DE DATOS ---
class Log(db.Model):
    """
    Modelo para persistir el historial de mensajes recibidos.
    Se utiliza para auditoría y visualización en el dashboard (index.html).
    """
    id = db.Column(db.Integer, primary_key=True)
    fecha_y_hora = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    texto = db.Column(db.TEXT)

# Creación de tablas dentro del contexto de la aplicación
with app.app_context():
    db.create_all()

# --- CONTROLADORES DE RUTA (ENDPOINTS) ---

@app.route('/', methods=['GET'])
def index():
    """
    Dashboard principal: Recupera y muestra los logs almacenados en orden descendente.
    """
    registros = Log.query.order_by(Log.fecha_y_hora.desc()).all()
    return render_template('index.html', registros=registros)

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    """
    Punto de enlace para el Webhook de Meta. 
    Maneja la verificación (GET) y la recepción de eventos (POST).
    """
    if request.method == 'GET':
        # Validación del Webhook requerida por el panel de desarrolladores de Meta
        verify_token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        # 'ANDERCODE' debe coincidir con el token configurado en el portal de Meta
        if challenge and verify_token == 'ANDERCODE':
            return challenge, 200
        return "Token de verificación inválido", 401
    
    elif request.method == 'POST':
        data = request.get_json()
        print(f"LOG: Payload recibido -> {json.dumps(data)}", flush=True)

        try:
            # Navegación en el objeto JSON de WhatsApp Cloud API
            entry = data['entry'][0]
            changes = entry['changes'][0]
            value = changes['value']

            if 'messages' in value:
                message_obj = value['messages'][0]
                wa_id = message_obj['from'] # ID del remitente

                # --- CORRECCIÓN PARA NÚMEROS DE MÉXICO (Error #131030) ---
                # Meta suele enviar el log con '521', pero el Sandbox espera '52' sin el 1.
                # Esta lógica normaliza el número antes de procesar la respuesta.
                if wa_id.startswith("521") and len(wa_id) == 13:
                    wa_id = "52" + wa_id[3:]
                    print(f"DEBUG: Número normalizado para México -> {wa_id}", flush=True)

                # Persistencia del mensaje en la base de datos
                nuevo_log = Log(texto=json.dumps(message_obj))
                db.session.add(nuevo_log)
                db.session.commit()

                # Extracción de contenido según el tipo de mensaje
                if 'text' in message_obj:
                    msg_text = message_obj['text']['body']
                    procesar_respuesta(msg_text, wa_id)
                    
                elif 'interactive' in message_obj:
                    # Soporte para respuestas de botones o listas
                    interactive_obj = message_obj['interactive']
                    tipo_i = interactive_obj['type']
                    # El ID del elemento suele ser la clave para la lógica del bot
                    msg_text = interactive_obj[tipo_i]['id']
                    procesar_respuesta(msg_text, wa_id)
            
            return jsonify({"status": "ok"}), 200
            
        except Exception as e:
            print(f"ERROR: Fallo al procesar el webhook -> {str(e)}", flush=True)
            return jsonify({"status": "error"}), 200

# --- LÓGICA DE NEGOCIO (BOT) ---

def procesar_respuesta(texto, numero):
    """
    Determina la respuesta automática basándose en palabras clave.
    """
    texto = texto.lower().strip()

    if "hola" in texto:
        respuesta = "🚀 ¡Hola! Bienvenido al bot de respuesta automática.\n\nEscribe *1* para recibir información técnica."
    elif "1" in texto:
        respuesta = "✅ *Opción 1 seleccionada*: Este bot está corriendo sobre Python 3 y Flask en servidores de Render."
    else:
        respuesta = "🤖 *Menú Principal*\n\n1. Información Técnica\n2. Ubicación\n\nEnvía 'Hola' para ver este menú."

    enviar_a_whatsapp(respuesta, numero)

def enviar_a_whatsapp(cuerpo, numero):
    """
    Realiza la petición HTTP POST a la Graph API de Meta para enviar el mensaje.
    """
    # Priorizar variables de entorno para seguridad; fallback a valores de desarrollo
    token_acceso = os.environ.get("WHATSAPP_TOKEN", "TU_TOKEN_TEMPORAL_AQUI")
    phone_id = os.environ.get("PHONE_ID", "1077626325424911")

    payload = json.dumps({
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": numero,
        "type": "text",
        "text": {"body": cuerpo}
    })

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token_acceso}"
    }

    # Implementación nativa con http.client (evita dependencias externas como 'requests')
    conn = http.client.HTTPSConnection("graph.facebook.com")
    try:
        # v19.0 es la versión estable recomendada para integraciones educativas
        conn.request("POST", f"/v19.0/{phone_id}/messages", payload, headers)
        res = conn.getresponse()
        data_res = res.read().decode()
        
        # Log de diagnóstico para verificar el estado en el panel de Render
        print(f"META API RESPONSE: {res.status} - {data_res}", flush=True)
        
    except Exception as e:
        print(f"SYSTEM ERROR: Error de conexión con Meta -> {e}", flush=True)
    finally:
        conn.close()

# --- ENTRADA DE LA APLICACIÓN ---

if __name__ == '__main__':
    # Configuración dinámica de puerto para compatibilidad con el entorno de Render
    port = int(os.environ.get("PORT", 10000))
    # 'host=0.0.0.0' es imperativo para permitir conexiones externas al contenedor
    app.run(host='0.0.0.0', port=port, debug=True)