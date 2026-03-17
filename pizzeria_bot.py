from models import db, Cliente, Pedido
import json

# --- DATOS DEL NEGOCIO ---
MENU_PIZZAS = {"familiar": 150, "mediana": 130, "chica": 80}
MENU_EXTRAS = {"spagguetti": 80, "ensalada": 60, "queso": 100, "soda": 50}
INGREDIENTES = [
    "Jamón", "Salami", "Peperoni", "Tocino", "Machaca", "Jalapeño", 
    "Aceituna", "Atún", "Salchicha", "Champiñones", "Pimientos", 
    "Tomate", "Chorizo", "Piña", "Elote", "Cereza", "Chilorio", "Cebolla"
]

sesiones = {} # Diccionario temporal para estados

class PizzeriaBot:
    def __init__(self, config, wa_service):
        self.wa = wa_service
        self.config = config

    def gestionar_flujo(self, wa_id, texto, inter_id=None):
        """Controlador central de la conversación."""
        # Limpiar número
        if wa_id.startswith("521"): wa_id = "52" + wa_id[3:]
        
        # Inicializar sesión si no existe
        if wa_id not in sesiones:
            sesiones[wa_id] = {"paso": "INICIO", "pedido": {"ingredientes": [], "extras": []}, "total": 0}
        
        s = sesiones[wa_id]
        cliente = Cliente.query.filter_by(telefono=wa_id).first()

        # 1. BIENVENIDA Y TAMAÑOS
        if s["paso"] == "INICIO" or texto.lower() == "hola":
            s["paso"] = "TAMAÑO"
            saludo = f"🍕 ¡Hola *{cliente.nombre if cliente else 'amigo'}*! Bienvenido a Mesa Code Pizza.\n\n¿Qué tamaño de pizza te gustaría ordenar hoy?"
            rows = [{"id": k, "title": k.capitalize(), "description": f"${v}"} for k, v in MENU_PIZZAS.items()]
            return self.wa.enviar_lista(wa_id, "Menú de Pizzas", saludo, "Elige una opción:", "Ver Tamaños", [{"title": "Pizzas", "rows": rows}])

        # 2. SELECCIÓN DE INGREDIENTES
        if s["paso"] == "TAMAÑO":
            s["pedido"]["tamano"] = inter_id
            s["total"] += MENU_PIZZAS[inter_id]
            s["paso"] = "INGREDIENTES"
            rows = [{"id": f"ing_{i}", "title": ing} for i, ing in enumerate(INGREDIENTES)]
            # Agregamos opción para terminar si ya no quiere más
            rows.append({"id": "fin_ing", "title": "🏁 Terminar selección", "description": "Usa esto si ya no quieres más ingredientes"})
            
            body = f"Has elegido Pizza {inter_id.capitalize()}.\n\nSelecciona tus ingredientes (3 incluidos, adicionales +$20):"
            return self.wa.enviar_lista(wa_id, "Ingredientes", body, "Selecciona de la lista:", "Ver Ingredientes", [{"title": "Ingredientes", "rows": rows}])

        if s["paso"] == "INGREDIENTES":
            if inter_id == "fin_ing":
                return self._pasar_a_extras(wa_id, s)
            
            ing_nombre = INGREDIENTES[int(inter_id.split("_")[1])]
            if ing_nombre not in s["pedido"]["ingredientes"]:
                s["pedido"]["ingredientes"].append(ing_nombre)
                if len(s["pedido"]["ingredientes"]) > 3:
                    s["total"] += 20 # Cobro extra
            
            cant = len(s["pedido"]["ingredientes"])
            body = f"✅ *{ing_nombre}* añadido ({cant}/3 gratis).\n\n¿Deseas agregar otro o terminar?"
            buttons = [{"id":"fin_ing","title":"🏁 Terminar"}, {"id":"seguir","title":"➕ Otro ingrediente"}]
            return self.wa.enviar_botones(wa_id, body, buttons)

        # 3. EXTRAS
        if s["paso"] == "EXTRAS":
            if inter_id == "fin_ext":
                return self._preguntar_entrega(wa_id, s, cliente)
            
            extra_data = MENU_EXTRAS.get(inter_id)
            if extra_data:
                s["pedido"]["extras"].append(inter_id)
                s["total"] += extra_data
                return self.wa.enviar_botones(wa_id, f"✅ *{inter_id.capitalize()}* añadido. ¿Algo más?", [{"id":"fin_ext","title":"🏁 Finalizar"}, {"id":"mas_ext","title":"🥤 Ver Extras"}])

        # 4. ENTREGA Y DIRECCIÓN
        if s["paso"] == "TIPO_ENTREGA":
            s["pedido"]["entrega"] = "domicilio" if inter_id == "dom" else "recoger"
            if inter_id == "rec": return self._finalizar_orden(wa_id, s, cliente)
            
            if cliente and cliente.ultima_direccion:
                s["paso"] = "CONFIRMAR_DIR"
                msg = f"¿Usamos la dirección de tu último pedido?\n📍 {cliente.ultima_direccion}"
                return self.wa.enviar_botones(wa_id, msg, [{"id":"dir_si","title":"✅ Sí"},{"id":"dir_no","title":"✏️ Nueva"}])
            
            s["paso"] = "PEDIR_NOMBRE"
            return self.wa.enviar_texto(wa_id, "Para el envío, ¿cuál es tu nombre?")

        if s["paso"] == "PEDIR_NOMBRE":
            s["pedido"]["nombre"] = texto
            s["paso"] = "PEDIR_DIR"
            return self.wa.enviar_texto(wa_id, "Perfecto, ahora dime tu dirección completa:")

        if s["paso"] == "PEDIR_DIR":
            s["pedido"]["direccion"] = texto
            self._guardar_cliente(wa_id, s["pedido"].get("nombre"), texto)
            return self._finalizar_orden(wa_id, s, cliente)

        if s["paso"] == "CONFIRMAR_DIR":
            if inter_id == "dir_si":
                s["pedido"]["direccion"] = cliente.ultima_direccion
                return self._finalizar_orden(wa_id, s, cliente)
            s["paso"] = "PEDIR_DIR"
            return self.wa.enviar_texto(wa_id, "Dime la nueva dirección de entrega:")

    # --- FUNCIONES AUXILIARES ---
    def _pasar_a_extras(self, wa_id, s):
        s["paso"] = "EXTRAS"
        rows = [{"id": k, "title": k.capitalize(), "description": f"${v}"} for k, v in MENU_EXTRAS.items()]
        rows.append({"id": "fin_ext", "title": "🏁 No, gracias", "description": "Continuar al pago"})
        return self.wa.enviar_lista(wa_id, "Extras", "¿Gustas agregar algún extra o bebida?", "Mesa Code Pizza", "Ver Extras", [{"title": "Extras", "rows": rows}])

    def _preguntar_entrega(self, wa_id, s, cliente):
        s["paso"] = "TIPO_ENTREGA"
        return self.wa.enviar_botones(wa_id, "¿Tu pedido es a domicilio o pasas a recoger?", [{"id":"dom","title":"🛵 Domicilio"},{"id":"rec","title":"🛍️ Recoger"}])

    def _guardar_cliente(self, tel, nom, dir):
        c = Cliente.query.filter_by(telefono=tel).first()
        if not c: c = Cliente(telefono=tel)
        if nom: c.nombre = nom
        c.ultima_direccion = dir
        db.session.add(c)
        db.session.commit()

    def _finalizar_orden(self, wa_id, s, cliente):
        # Crear registro en BD
        p = Pedido(cliente_id=cliente.id if cliente else None, total=s["total"], detalles_json=json.dumps(s["pedido"]), tipo_entrega=s["pedido"]["entrega"])
        db.session.add(p)
        db.session.commit()

        # Generar Ticket
        ticket = f"🧾 *TICKET DE ORDEN #{p.id}*\n"
        ticket += f"🍕 Pizza {s['pedido']['tamano'].capitalize()}\n"
        ticket += f"🧀 Ingredientes: {', '.join(s['pedido']['ingredientes'])}\n"
        if s["pedido"]["extras"]: ticket += f"🥤 Extras: {', '.join(s['pedido']['extras'])}\n"
        ticket += f"📍 Entrega: {s['pedido']['entrega'].capitalize()}\n"
        ticket += f"💰 *TOTAL: ${s['total']}*\n\n"
        ticket += "⏳ Tiempo de espera: *40 minutos*.\n¡Gracias por tu compra!"
        
        sesiones.pop(wa_id)
        return self.wa.enviar_texto(wa_id, ticket)