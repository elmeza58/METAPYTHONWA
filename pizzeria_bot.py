from models import db, Cliente, Pedido
import json

MENU_PIZZAS = {"familiar": 150, "mediana": 130, "chica": 80}
MENU_EXTRAS = {"spagguetti": 80, "ensalada": 60, "queso": 100, "soda": 50}
INGREDIENTES = [
    "Jamón", "Salami", "Peperoni", "Tocino", "Machaca", "Jalapeño", 
    "Aceituna", "Atún", "Salchicha", "Champiñones", "Pimientos", 
    "Tomate", "Chorizo", "Piña", "Elote", "Cereza", "Chilorio", "Cebolla"
]

sesiones = {}

class PizzeriaBot:
    def __init__(self, config, wa_service):
        self.wa = wa_service
        self.config = config

    def gestionar_mensaje(self, wa_id, texto, inter_id=None):
        if wa_id.startswith("521"): wa_id = "52" + wa_id[3:]
        
        if wa_id not in sesiones:
            sesiones[wa_id] = {"paso": "INICIO", "pedido": {"ingredientes": [], "extras": []}, "total": 0}
        
        s = sesiones[wa_id]
        cliente = Cliente.query.filter_by(telefono=wa_id).first()

        # 1. BIENVENIDA
        if s["paso"] == "INICIO" or texto.lower() == "hola":
            s["paso"] = "TAMAÑO"
            nombre_display = cliente.nombre if (cliente and cliente.nombre) else "amigo"
            saludo = f"🍕 ¡Hola *{nombre_display}*! Bienvenido a Mesa Code Pizza.\n\n¿Qué tamaño de pizza te gustaría ordenar hoy?"
            rows = [{"id": k, "title": k.capitalize(), "description": f"${v}"} for k, v in MENU_PIZZAS.items()]
            return self.wa.enviar_lista(wa_id, "Menú de Pizzas", saludo, "Elige una opción:", "Ver Tamaños", [{"title": "Pizzas", "rows": rows}])

        # 2. INGREDIENTES
        if s["paso"] == "TAMAÑO":
            s["pedido"]["tamano"] = inter_id
            s["total"] += MENU_PIZZAS[inter_id]
            s["paso"] = "INGREDIENTES"
            return self._enviar_lista_ingredientes(wa_id, s)

        if s["paso"] == "INGREDIENTES":
            if inter_id == "fin_ing":
                return self._pasar_a_extras(wa_id, s)
            
            ing_nombre = INGREDIENTES[int(inter_id.split("_")[1])]
            if ing_nombre not in s["pedido"]["ingredientes"]:
                s["pedido"]["ingredientes"].append(ing_nombre)
                if len(s["pedido"]["ingredientes"]) > 3:
                    s["total"] += 20 # Cobro extra por ingrediente adicional
            
            cant = len(s["pedido"]["ingredientes"])
            body = f"✅ *{ing_nombre}* añadido ({cant}/3 incluidos).\n\n¿Deseas agregar otro o pasar a los extras?"
            buttons = [{"id":"fin_ing","title":"🏁 Finalizar ingredientes"}, {"id":"seguir_ing","title":"➕ Otro ingrediente"}]
            return self.wa.enviar_botones(wa_id, body, buttons)
            
        if texto == "➕ Otro ingrediente":
            return self._enviar_lista_ingredientes(wa_id, s)

        # 3. EXTRAS
        if s["paso"] == "EXTRAS":
            if inter_id == "fin_ext":
                return self._preguntar_entrega(wa_id, s, cliente)
            
            if inter_id in MENU_EXTRAS:
                s["pedido"]["extras"].append(inter_id)
                s["total"] += MENU_EXTRAS[inter_id]
                return self.wa.enviar_botones(wa_id, f"✅ *{inter_id.capitalize()}* añadido. ¿Gustas algo más?", [{"id":"fin_ext","title":"🏁 No, gracias"}, {"id":"mas_ext","title":"🥤 Ver Extras"}])
            
            if inter_id == "mas_ext" or texto == "🥤 Ver Extras":
                return self._pasar_a_extras(wa_id, s)

        # 4. ENTREGA Y DIRECCIÓN
        if s["paso"] == "TIPO_ENTREGA":
            s["pedido"]["entrega"] = "domicilio" if inter_id == "dom" else "recoger"
            if inter_id == "rec": return self._finalizar_orden(wa_id, s, cliente)
            
            if cliente and cliente.ultima_direccion:
                s["paso"] = "CONFIRMAR_DIR"
                msg = f"📍 He guardado tu dirección anterior:\n_{cliente.ultima_direccion}_\n\n¿Deseas usar la misma o cambiarla?"
                return self.wa.enviar_botones(wa_id, msg, [{"id":"dir_si","title":"✅ Usar la misma"},{"id":"dir_no","title":"✏️ Cambiar"}])
            
            s["paso"] = "PEDIR_NOMBRE"
            return self.wa.enviar_texto(wa_id, "Para tu entrega a domicilio, ¿cuál es tu nombre?")

        if s["paso"] == "PEDIR_NOMBRE":
            s["pedido"]["nombre"] = texto
            s["paso"] = "PEDIR_DIR"
            return self.wa.enviar_texto(wa_id, f"Mucho gusto {texto}. Ahora dime tu dirección completa (Calle, Número y Colonia):")

        if s["paso"] == "PEDIR_DIR":
            s["pedido"]["direccion"] = texto
            self._guardar_cliente(wa_id, s["pedido"].get("nombre"), texto)
            return self._finalizar_orden(wa_id, s, cliente)

        if s["paso"] == "CONFIRMAR_DIR":
            if inter_id == "dir_si":
                s["pedido"]["direccion"] = cliente.ultima_direccion
                return self._finalizar_orden(wa_id, s, cliente)
            s["paso"] = "PEDIR_DIR"
            return self.wa.enviar_texto(wa_id, "Entendido, dime la nueva dirección de entrega:")

    # --- PRIVADAS ---
    def _enviar_lista_ingredientes(self, wa_id, s):
        rows = [{"id": f"ing_{i}", "title": ing} for i, ing in enumerate(INGREDIENTES)]
        body = f"Selecciona tus ingredientes para la Pizza {s['pedido']['tamano'].capitalize()}.\n\nRecuerda: 3 incluidos, adicionales +$20 c/u."
        return self.wa.enviar_lista(wa_id, "Ingredientes", body, "Mesa Code Pizza", "Ver Lista", [{"title": "Ingredientes", "rows": rows}])

    def _pasar_a_extras(self, wa_id, s):
        s["paso"] = "EXTRAS"
        rows = [{"id": k, "title": k.capitalize(), "description": f"${v}"} for k, v in MENU_EXTRAS.items()]
        return self.wa.enviar_lista(wa_id, "Menú de Extras", "¿Gustas acompañar tu pizza con algún extra o bebida?", "Mesa Code Pizza", "Ver Extras", [{"title": "Complementos", "rows": rows}])

    def _preguntar_entrega(self, wa_id, s, cliente):
        s["paso"] = "TIPO_ENTREGA"
        return self.wa.enviar_botones(wa_id, "¿Tu pedido es para entregar a domicilio o pasas a recoger?", [{"id":"dom","title":"🛵 Domicilio"},{"id":"rec","title":"🛍️ Recoger"}])

    def _guardar_cliente(self, tel, nom, dir):
        c = Cliente.query.filter_by(telefono=tel).first()
        if not c: c = Cliente(telefono=tel)
        if nom: c.nombre = nom
        c.ultima_direccion = dir
        db.session.add(c)
        db.session.commit()

    def _finalizar_orden(self, wa_id, s, cliente):
        p = Pedido(cliente_id=cliente.id if cliente else None, total=s["total"], detalles_json=json.dumps(s["pedido"]), tipo_entrega=s["pedido"]["entrega"])
        db.session.add(p)
        db.session.commit()

        # Ticket Profesional
        ticket = f"🧾 *TICKET DE ORDEN #{p.id}*\n"
        ticket += f"━━━━━━━━━━━━━━\n"
        ticket += f"🍕 *Pizza {s['pedido']['tamano'].capitalize()}*\n"
        ticket += f"🧀 Ing: {', '.join(s['pedido']['ingredientes'])}\n"
        if s['pedido']['extras']: ticket += f"🥤 Ext: {', '.join(s['pedido']['extras'])}\n"
        ticket += f"📍 Entrega: {s['pedido']['entrega'].capitalize()}\n"
        if s['pedido']['entrega'] == "domicilio": ticket += f"🏠 Dir: {s['pedido']['direccion']}\n"
        ticket += f"━━━━━━━━━━━━━━\n"
        ticket += f"💰 *TOTAL A PAGAR: ${s['total']}*\n"
        ticket += f"⏳ Tiempo de espera: *40 min*\n\n"
        ticket += "¡Gracias por elegir Mesa Code Pizza! 🍕🔥"
        
        sesiones.pop(wa_id)
        return self.wa.enviar_texto(wa_id, ticket)