from whatsapp_service import WhatsAppService
from models import db, Cliente, Pedido
import json
from datetime import datetime

# --- DATOS DEL MENÚ - Extraídos de tus imágenes ---
MENU_PIZZAS = {
    'piz_familiar': {'nombre': 'Pizza familiar', 'precio': 150.0},
    'piz_mediana': {'nombre': 'Pizza mediana', 'precio': 130.0},
    'piz_chica': {'nombre': 'Pizza chica', 'precio': 80.0},
}

OFERTAS = {
    'of_2_familiar': {'nombre': '2 Familiar', 'precio': 280.0},
    'of_2_mediana': {'nombre': '2 medianas', 'precio': 240.0},
}

EXTRAS = {
    'ext_spaguetti': {'nombre': 'Espaguetti', 'precio': 80.0},
    'ext_ensalada': {'nombre': 'Ensalada', 'precio': 60.0},
    'ext_queso': {'nombre': 'Queso extra', 'precio': 100.0},
    'ext_soda': {'nombre': 'Soda', 'precio': 30.0}, # Soda no tenía precio, asignamos 30
}

# Ingredientes de image_3.png
INGREDIENTES_TODOS = [
    'jamón', 'salami', 'peperoni', 'tocino', 'machaca', 'jalapeño', 'aceituna', 'atún', 'salchicha',
    'champiñones', 'pimientos', 'tomate', 'chorizo', 'piña', 'elote', 'cereza', 'chilorio', 'cebolla'
]

MAX_INGREDIENTES_INCLUIDOS = 3
COSTO_INGREDIENTE_EXTRA = 15.0 # Definimos un costo extra razonable

# --- MÁQUINA DE ESTADOS Y GESTIÓN DE PEDIDOS TEMPORALES ---
# Usamos un diccionario simple en memoria. Para escalabilidad comercial,
# esto debería guardarse en una base de datos Redis.
conversation_states = {} 
current_orders_temp = {}

# Constantes de Estado
STATE_INICIO = 'inicio'
STATE_SELECCION_TAMAÑO = 'seleccion_tamaño'
STATE_SELECCION_INGREDIENTES = 'seleccion_ingredientes'
STATE_CONFIRMACION_INGREDIENTES = 'confirmacion_ingredientes'
STATE_SELECCION_EXTRAS = 'seleccion_extras'
STATE_PREGUNTA_ENTREGA = 'pregunta_entrega'
STATE_SOLICITUD_NOMBRE = 'solicitud_nombre'
STATE_SOLICITUD_DIRECCION = 'solicitud_direccion'
STATE_CONFIRMACION_DIRECCION_EXISTENTE = 'confirmacion_direccion_existente'
STATE_CONFIRMACION_FINAL = 'confirmacion_final'

class PizzeriaBot:
    """Maneja la lógica de la conversación del bot de pizzería."""
    
    def __init__(self):
        self.wa = WhatsAppService()

    def procesar_mensaje_entrante(self, to_number, text_input, interactive_input=None):
        """Procesa cualquier mensaje entrante y determina la respuesta según el estado."""
        wa_id = to_number
        text_input = text_input.lower().strip()
        state = conversation_states.get(wa_id, STATE_INICIO)
        
        print(f"LOG: Cliente {wa_id} en estado '{state}' envió: '{text_input}'")

        if state == STATE_INICIO or text_input in ['hola', 'inicio', 'menú']:
            return self._iniciar_conversacion(wa_id)

        # Lógica de estados para el flujo del pedido
        handlers = {
            STATE_SELECCION_TAMAÑO: self._manejar_seleccion_tamaño,
            STATE_SELECCION_INGREDIENTES: self._manejar_seleccion_ingredientes,
            STATE_SELECCION_EXTRAS: self._manejar_seleccion_extras,
            STATE_PREGUNTA_ENTREGA: self._manejar_pregunta_entrega,
            STATE_SOLICITUD_NOMBRE: self._manejar_solicitud_nombre,
            STATE_SOLICITUD_DIRECCION: self._manejar_solicitud_direccion,
            STATE_CONFIRMACION_DIRECCION_EXISTENTE: self._manejar_confirmacion_direccion_existente,
            STATE_CONFIRMACION_FINAL: self._manejar_confirmacion_final,
        }

        handler = handlers.get(state)
        if handler:
            return handler(wa_id, text_input, interactive_input)
        else:
            return self._iniciar_conversacion(wa_id) # Volver al inicio por seguridad

    def _iniciar_conversacion(self, wa_id):
        """Saluda y muestra el menú principal interactivo."""
        conversation_states[wa_id] = STATE_SELECCION_TAMAÑO
        current_orders_temp[wa_id] = {'pizzas': [], 'extras': []} # Reset pedido temporal
        
        # Primero, verificamos si es cliente existente para personalizar el saludo
        cliente = Cliente.query.filter_by(telefono=wa_id).first()
        
        saludo = "🚀 ¡Hola! Bienvenido a MESA CODE PIZZERÍA.\n"
        if cliente and cliente.nombre:
            saludo = f"🚀 ¡Hola *{cliente.nombre}*! Qué gusto tenerte de vuelta en MESA CODE PIZZERÍA.\n"
        
        header = "🍕 Nuestro Menú"
        body = saludo + "¿Qué tamaño de pizza deseas ordenar?"
        footer = "Selecciona de la lista 👇"
        button_text = "Ver Tamaños"
        
        # Creación de secciones para la lista interactiva extraídos de image_2.png
        sections = [
            {
                "title": "Pizzas Individuales",
                "rows": [
                    {"id": id_p, "title": data['nombre'], "description": f"${data['precio']:.2f}"}
                    for id_p, data in MENU_PIZZAS.items()
                ]
            },
            {
                "title": "Ofertas del día",
                "rows": [
                    {"id": id_o, "title": data['nombre'], "description": f"${data['precio']:.2f}"}
                    for id_o, data in OFERTAS.items()
                ]
            }
        ]
        
        return self.wa.enviar_lista(wa_id, header, body, footer, button_text, sections)

    def _manejar_seleccion_tamaño(self, wa_id, text_input, interactive_input):
        """Recibe el tamaño de pizza elegido y pasa a la selección de ingredientes."""
        selected_id = interactive_input or text_input
        pizza = MENU_PIZZAS.get(selected_id) or OFERTAS.get(selected_id)
        
        if not pizza:
            return self.wa.enviar_texto(wa_id, "⚠️ Por favor, selecciona una opción válida del menú.")
            
        # Guardar en pedido temporal
        order = current_orders_temp.get(wa_id)
        order['pizzas'].append({'id': selected_id, 'nombre': pizza['nombre'], 'precio': pizza['precio'], 'ingredientes': []})
        
        conversation_states[wa_id] = STATE_SELECCION_INGREDIENTES
        
        header = "🧀 Elige tus Ingredientes"
        body = f"Perfecto, has elegido {pizza['nombre']}.\n"
        body += f"Elige hasta *{MAX_INGREDIENTES_INCLUIDOS}* ingredientes incluidos."
        footer = "Cada ingrediente extra tiene un costo de $15."
        button_text = "Ver Ingredientes"
        
        # Secciones de ingredientes para image_3.png
        # Para escalabilidad, dividimos en 2 secciones
        mid = len(INGREDIENTES_TODOS) // 2
        sections = [
            {
                "title": "Ingredientes Clásicos",
                "rows": [{"id": f"ing_{i}", "title": ing.capitalize()} for i, ing in enumerate(INGREDIENTES_TODOS[:mid])]
            },
            {
                "title": "Ingredientes Especiales",
                "rows": [{"id": f"ing_{i+mid}", "title": ing.capitalize()} for i, ing in enumerate(INGREDIENTES_TODOS[mid:])]
            }
        ]
        
        # Añadimos un botón al menú principal para confirmar los ingredientes actuales
        sections.append({
            "title": "Finalizar Selección",
            "rows": [{"id": "confirmar_ingredientes", "title": "Confirmar ingredientes y seguir", "description": "Usa esto para no añadir más."}]
        })
        
        return self.wa.enviar_lista(wa_id, header, body, footer, button_text, sections)

    def _manejar_seleccion_ingredientes(self, wa_id, text_input, interactive_input):
        """Recibe ingredientes secuencialmente y actualiza el costo si hay extras."""
        selected_id = interactive_input or text_input
        order = current_orders_temp.get(wa_id)
        current_pizza = order['pizzas'][-1]
        
        if selected_id == "confirmar_ingredientes":
            return self._pasar_a_extras(wa_id)
            
        try:
            ing_idx = int(selected_id.replace('ing_', ''))
            ing_nombre = INGREDIENTES_TODOS[ing_idx].capitalize()
        except (ValueError, IndexError):
            return self.wa.enviar_texto(wa_id, "⚠️ Por favor, selecciona un ingrediente de la lista.")

        if ing_nombre in current_pizza['ingredientes']:
            return self.wa.enviar_texto(wa_id, f"⚠️ Ya has seleccionado {ing_nombre}. Por favor elige otro.")

        current_pizza['ingredientes'].append(ing_nombre)
        num_ing = len(current_pizza['ingredientes'])
        
        if num_ing < MAX_INGREDIENTES_INCLUIDOS:
            # Botones interactivos para facilidad
            buttons = [
                {"id": "confirmar_ingredientes", "title": "No añadir más ✅"},
                {"id": "inicio", "title": "Reiniciar menú 🔄"}
            ]
            text = f"✅ Ingrediente *{num_ing}/{MAX_INGREDIENTES_INCLUIDOS}* añadido: {ing_nombre}.\n"
            text += f"Te quedan {MAX_INGREDIENTES_INCLUIDOS - num_ing} incluidos.\n\nElige otro de la lista arriba o presiona confirmar:"
            return self.wa.enviar_botones(wa_id, text, buttons)
            
        else:
            # Ya se eligieron los 3 incluidos
            costo_extra = (num_ing - MAX_INGREDIENTES_INCLUIDOS) * COSTO_INGREDIENTE_EXTRA
            current_pizza['precio_extra_ingredientes'] = costo_extra
            
            # Pasar automáticamente a extras tras el 3er ingrediente
            text = f"✅ Ingrediente {num_ing} añadido: {ing_nombre}.\n"
            text += f"Has seleccionado {MAX_INGREDIENTES_INCLUIDOS} ingredientes incluidos.\n"
            if costo_extra > 0:
                text += f"Costo extra por ingredientes: ${costo_extra:.2f}.\n\nSigamos con los extras..."
            else:
                text += "\nSigamos con los extras..."
                
            self.wa.enviar_texto(wa_id, text)
            return self._pasar_a_extras(wa_id)

    def _pasar_a_extras(self, wa_id):
        """Muestra el menú interactivo de extras."""
        conversation_states[wa_id] = STATE_SELECCION_EXTRAS
        
        header = "🥤 Añade un Extra"
        body = "¿Deseas complementar tu pedido con alguno de nuestros extras?"
        footer = "Extraídos de image_2.png"
        button_text = "Ver Extras"
        
        sections = [
            {
                "title": "Para Acompañar",
                "rows": [{"id": id_e, "title": data['nombre'], "description": f"${data['precio']:.2f}"} for id_e, data in EXTRAS.items()]
            },
            {
                "title": "Finalizar Pedido",
                "rows": [{"id": "confirmar_extras", "title": "Finalizar sin añadir extras ✅", "description": "Usa esto para no añadir más."}]
            }
        ]
        return self.wa.enviar_lista(wa_id, header, body, footer, button_text, sections)

    def _manejar_seleccion_extras(self, wa_id, text_input, interactive_input):
        """Recibe extras elegidos secuencialmente."""
        selected_id = interactive_input or text_input
        
        if selected_id == "confirmar_extras":
            return self._preguntar_tipo_entrega(wa_id)
            
        extra = EXTRAS.get(selected_id)
        if not extra:
             return self.wa.enviar_texto(wa_id, "⚠️ Por favor, selecciona una opción válida de los extras.")

        order = current_orders_temp.get(wa_id)
        order['extras'].append({'id': selected_id, 'nombre': extra['nombre'], 'precio': extra['precio']})
        
        # Botones para continuar
        buttons = [
            {"id": "confirmar_extras", "title": "No añadir más ✅"},
            {"id": "inicio", "title": "Reiniciar menú 🔄"}
        ]
        text = f"✅ Extra añadido: {extra['nombre']}.\n¿Deseas añadir otro o finalizar?"
        return self.wa.enviar_botones(wa_id, text, buttons)

    def _preguntar_tipo_entrega(self, wa_id):
        """Pregunta si el pedido será para entregar o recoger."""
        conversation_states[wa_id] = STATE_PREGUNTA_ENTREGA
        
        body = "¿Deseas que lo llevemos a domicilio 🛵 o pasarás a recogerlo 🛍️?"
        buttons = [
            {"id": "tipo_entrega_domicilio", "title": "🛵 A Domicilio"},
            {"id": "tipo_entrega_recogida", "title": "🛍️ Recoger"}
        ]
        return self.wa.enviar_botones(wa_id, body, buttons)

    def _manejar_pregunta_entrega(self, wa_id, text_input, interactive_input):
        """Recibe el tipo de entrega y determina los siguientes pasos de información."""
        selected_id = interactive_input or text_input
        order = current_orders_temp.get(wa_id)
        
        if selected_id == "tipo_entrega_domicilio":
            order['tipo_entrega'] = 'domicilio'
        elif selected_id == "tipo_entrega_recogida":
            order['tipo_entrega'] = 'recogida'
        else:
             return self.wa.enviar_texto(wa_id, "⚠️ Por favor, selecciona una opción de entrega válida.")

        # Verificar si es cliente existente para personalizar la atención
        cliente = Cliente.query.filter_by(telefono=wa_id).first()
        
        if order['tipo_entrega'] == 'domicilio':
            if cliente and cliente.ultima_direccion:
                # Cliente existente con dirección, preguntamos si reenviar
                conversation_states[wa_id] = STATE_CONFIRMACION_DIRECCION_EXISTENTE
                body = f"🚀 Veo que ya nos has ordenado antes.\n¿Deseas reenviar a la misma dirección guardada:\n*{cliente.ultima_direccion}*?"
                buttons = [
                    {"id": "mismo_domicilio", "title": "✅ Sí, mismo lugar"},
                    {"id": "nueva_direccion", "title": "✏️ Nueva dirección"}
                ]
                return self.wa.enviar_botones(wa_id, body, buttons)
            else:
                # Nuevo cliente o sin dirección para domicilio, solicitamos nombre
                conversation_states[wa_id] = STATE_SOLICITUD_NOMBRE
                return self.wa.enviar_texto(wa_id, "Perfecto, 🛵 para llevar.\n¿Cuál es tu nombre para el pedido?")
        
        else: # recogida
             # Para recogida, solicitamos nombre siempre (para personalizar o guardar si es nuevo)
             conversation_states[wa_id] = STATE_SOLICITUD_NOMBRE
             return self.wa.enviar_texto(wa_id, "Perfecto, 🛍️ para recoger.\n¿Cuál es tu nombre para el pedido?")

    def _manejar_solicitud_nombre(self, wa_id, text_input, interactive_input):
        """Recibe el nombre y decide si pedir dirección para domicilio."""
        if interactive_input: return # Ignorar clics accidentales de botones anteriores
        
        order = current_orders_temp.get(wa_id)
        order['nombre_cliente'] = text_input
        
        # Guardar/Actualizar cliente en DB
        cliente = Cliente.query.filter_by(telefono=wa_id).first()
        if not cliente:
            cliente = Cliente(telefono=wa_id, nombre=text_input)
            db.session.add(cliente)
        else:
            cliente.nombre = text_input # Actualizar nombre si cambió
        db.session.commit()

        if order['tipo_entrega'] == 'domicilio':
            conversation_states[wa_id] = STATE_SOLICITUD_DIRECCION
            return self.wa.enviar_texto(wa_id, f"Mucho gusto {text_input}.\n¿Cuál es la calle y número para el envío?")
        else:
             # recogida, pasamos a confirmación final
             return self._mostrar_resumen_y_confirmar(wa_id)

    def _manejar_solicitud_direccion(self, wa_id, text_input, interactive_input):
        """Recibe la dirección y pasa a la confirmación final."""
        if interactive_input: return
        
        order = current_orders_temp.get(wa_id)
        order['direccion_entrega'] = text_input
        
        # Actualizar dirección del cliente en DB
        cliente = Cliente.query.filter_by(telefono=wa_id).first()
        cliente.ultima_direccion = text_input
        db.session.commit()
        
        return self._mostrar_resumen_y_confirmar(wa_id)

    def _manejar_confirmacion_direccion_existente(self, wa_id, text_input, interactive_input):
        """Maneja la respuesta de usar dirección guardada o nueva."""
        selected_id = interactive_input or text_input
        order = current_orders_temp.get(wa_id)
        cliente = Cliente.query.filter_by(telefono=wa_id).first()
        
        if selected_id == "mismo_domicilio":
            order['direccion_entrega'] = cliente.ultima_direccion
            order['nombre_cliente'] = cliente.nombre # Usar nombre guardado
            return self._mostrar_resumen_y_confirmar(wa_id)
        elif selected_id == "nueva_direccion":
             # Solicitar dirección para domicilio
             conversation_states[wa_id] = STATE_SOLICITUD_DIRECCION
             return self.wa.enviar_texto(wa_id, "Entendido.\n¿Cuál es la nueva calle y número para el envío?")
        else:
             return self.wa.enviar_texto(wa_id, "⚠️ Por favor, selecciona una opción válida del botón.")

    def _manejar_confirmacion_final(self, wa_id, text_input, interactive_input):
        """Maneja el paso final de confirmación o cancelación."""
        selected_id = interactive_input or text_input
        
        if selected_id == "confirmar_pedido_final":
            return self._levantar_pedido_final(wa_id)
        elif selected_id == "cancelar_pedido":
             self.wa.enviar_texto(wa_id, "😞 Pedido cancelado. Esperamos verte de nuevo pronto.")
             return self._iniciar_conversacion(wa_id) # Volver al inicio
        else:
             return self.wa.enviar_texto(wa_id, "⚠️ Por favor, selecciona una opción válida del botón.")

    def _mostrar_resumen_y_confirmar(self, wa_id):
        """Calcula el costo total, muestra el resumen y pide la confirmación final."""
        order = current_orders_temp.get(wa_id)
        conversation_states[wa_id] = STATE_CONFIRMACION_FINAL
        
        total = 0.0
        pizzas_text = ""
        for i, p in enumerate(order['pizzas']):
            total_pizza = p['precio'] + p.get('precio_extra_ingredientes', 0.0)
            total += total_pizza
            ing_text = ", ".join(p['ingredientes'])
            pizzas_text += f"{i+1}. *{p['nombre']}* (${p['precio']:.2f})\n   Ing: {ing_text}"
            if p.get('precio_extra_ingredientes', 0.0) > 0:
                 pizzas_text += f" (+${p['precio_extra_ingredientes']:.2f} ing. extra)\n"
            else:
                 pizzas_text += "\n"
        
        extras_text = ""
        for i, e in enumerate(order['extras']):
            total += e['precio']
            extras_text += f"{i+1}. *{e['nombre']}* (${e['precio']:.2f})\n"

        order['costo_total'] = total

        body = f"🍕 *RESUMEN DEL PEDIDO*\n"
        body += f"👤 Cliente: {order['nombre_cliente']}\n"
        
        if order['tipo_entrega'] == 'domicilio':
            body += f"🛵 Entrega: A Domicilio\n📍 Dirección: {order['direccion_entrega']}\n\n"
        else:
            body += "🛍️ Entrega: Recoger en local\n\n"
            
        if pizzas_text:
            body += f"Pizzas:\n{pizzas_text}\n"
        if extras_text:
            body += f"Extras:\n{extras_text}\n"
            
        body += f"💰 *COSTO TOTAL: ${total:.2f}*\n\n"
        body += "¿Confirmas tu pedido final?"
        
        buttons = [
            {"id": "confirmar_pedido_final", "title": "✅ Sí, Confirmar"},
            {"id": "cancelar_pedido", "title": "😞 Cancelar"},
            {"id": "inicio", "title": "Reiniciar menú 🔄"}
        ]
        return self.wa.enviar_botones(wa_id, body, buttons)

    def _levantar_pedido_final(self, wa_id):
        """Guarda el pedido en la base de datos y notifica el tiempo estimado."""
        order = current_orders_temp.get(wa_id)
        cliente = Cliente.query.filter_by(telefono=wa_id).first()
        
        # Estructurar items para el JSON
        items_pedido = {
            'pizzas': order['pizzas'],
            'extras': order['extras']
        }
        
        # Levantar el pedido final en DB
        nuevo_pedido = Pedido(
            cliente_id=cliente.id,
            tipo_entrega=order['tipo_entrega'],
            direccion_entrega=order.get('direccion_entrega'),
            costo_total=order['costo_total'],
            items_json=json.dumps(items_pedido)
        )
        db.session.add(nuevo_pedido)
        db.session.commit()
        
        time_est = nuevo_pedido.tiempo_estimado
        
        if nuevo_pedido.tipo_entrega == 'domicilio':
            body = f"🎉✅ ¡Muchísimas gracias {cliente.nombre}!\n"
            body += f"Tu pedido se ha confirmado con éxito. En breve estará en camino a: {nuevo_pedido.direccion_entrega}.\n"
            body += f"🛵 Tiempo estimado de entrega: *{time_est} min*."
        else:
            body = f"🎉✅ ¡Muchísimas gracias {cliente.nombre}!\n"
            body += f"Tu pedido se ha confirmado con éxito.\n"
            body += f"🛍️ Puedes pasar a recogerlo en *{time_est} min*.\n¡Te esperamos!"
            
        self.wa.enviar_texto(wa_id, body)
        
        # Notificar al dueño de la pizzería (simulado)
        # Esto sería un envío de mensaje real al número del dueño.
        print(f"NOTIFICACIÓN DE NEGOCIO: Nuevo Pedido #{nuevo_pedido.id} levantado por ${nuevo_pedido.costo_total:.2f}")

        # Finalizar conversación y limpiar
        conversation_states[wa_id] = STATE_INICIO
        current_orders_temp.pop(wa_id, None)
        return 200 # Indica éxito