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
        
        # Reset total si el usuario escribe Hola para empezar de cero
        if texto.lower() == "hola":
            sesiones[wa_id] = {"paso": "INICIO", "pedido": {"ingredientes": [], "extras": []}, "total": 0}
        
        if wa_id not in sesiones:
            sesiones[wa_id] = {"paso": "INICIO", "pedido": {"ingredientes": [], "extras": []}, "total": 0}
        
        s = sesiones[wa_id]
        cliente = Cliente.query.filter_by(telefono=wa_id).first()

        # --- FLUJO CON ELIF (Solo entra en UN paso por mensaje) ---

        # 1. BIENVENIDA
        if s["paso"] == "INICIO":
            s["paso"] = "TAMAÑO"
            nombre_display = cliente.nombre if (cliente and cliente.nombre) else "amigo"
            saludo = f"🍕 ¡Hola *{nombre_display}*! Bienvenido a Mesa Code Pizza.\n\n¿Qué tamaño de pizza te gustaría ordenar hoy?"
            rows = [{"id": k, "title": k.capitalize(), "description": f"${v}"} for k, v in MENU_PIZZAS.items()]
            return self.wa.enviar_lista(wa_id, "Menú de Pizzas", saludo, "Elige una opción:", "Ver Tamaños", [{"title": "Pizzas", "rows": rows}])

        # 2. PROCESAR TAMAÑO Y PEDIR INGREDIENTES
        elif s["paso"] == "TAMAÑO":
            if not inter_id or inter_id not in MENU_PIZZAS:
                return self.wa.enviar_texto(wa_id, "⚠️ Por favor, selecciona un tamaño de la lista de arriba.")
            
            s["pedido"]["tamano"] = inter_id
            s["total"] += MENU_PIZZAS[inter_id]
            s["paso"] = "INGREDIENTES"
            return self._enviar_lista_ingredientes(wa_id, s)

        # 3. PROCESAR INGREDIENTES
        elif s["paso"] == "INGREDIENTES":
            if inter_id == "fin_ing" or texto == "🏁 Finalizar ingredientes":
                return self._pasar_a_extras(wa_id, s)
            
            # Validar que el ID sea de un ingrediente
            if inter_id and inter_id.startswith("ing_"):
                ing_idx = int(inter_id.split("_")[1])
                ing_nombre = INGREDIENTES[ing_idx]
                
                if ing_nombre not in s["pedido"]["ingredientes"]:
                    s["pedido"]["ingredientes"].append(ing_nombre)
                    if len(s["pedido"]["ingredientes"]) > 3:
                        s["total"] += 20 # Cobro extra
                
                cant = len(s["pedido"]["ingredientes"])
                body = f"✅ *{ing_nombre}* añadido ({cant}/3 incluidos).\n\n¿Deseas agregar otro o pasar a los extras?"
                buttons = [{"id":"fin_ing","title":"🏁 Finalizar"}, {"id":"seguir_ing","title":"➕ Otro ingrediente"}]
                return self.wa.enviar_botones(wa_id, body, buttons)
            
            elif texto == "➕ Otro ingrediente":
                return self._enviar_lista_ingredientes(wa_id, s)

        # 4. PROCESAR EXTRAS
        elif s["paso"] == "EXTRAS":
            if inter_id == "fin_ext" or texto == "🏁 No, gracias":
                return self._preguntar_entrega(wa_id, s, cliente)
            
            if inter_id in MENU_EXTRAS:
                s["pedido"]["extras"].append(inter_id)
                s["total"] += MENU_EXTRAS[inter_id]
                return self.wa.enviar_botones(wa_id, f"✅ *{inter_id.capitalize()}* añadido. ¿Gustas algo más?", [{"id":"fin_ext","title":"🏁 No, gracias"}, {"id":"mas_ext","title":"🥤 Ver Extras"}])
            
            if inter_id == "mas_ext" or texto == "🥤 Ver Extras":
                return self._pasar_a_extras(wa_id, s)

        # 5. TIPO DE ENTREGA
        elif s["paso"] == "TIPO_ENTREGA":
            s["pedido"]["entrega"] = "domicilio" if inter_id == "dom" else "recoger"
            if inter_id == "rec": return self._finalizar_orden(wa_id, s, cliente)
            
            if cliente and cliente.ultima_direccion:
                s["paso"] = "CONFIRMAR_DIR"
                msg = f"📍 ¿Enviamos a tu dirección anterior?\n_{cliente.ultima_direccion}_"
                return self.wa.enviar_botones(wa_id, msg, [{"id":"dir_si","title":"✅ Sí"},{"id":"dir_no","title":"✏️ Otra"}])
            
            s["paso"] = "PEDIR_NOMBRE"
            return self.wa.enviar_texto(wa_id, "Para el envío, ¿cuál es tu nombre?")

        # 6. DATOS DE ENVÍO
        elif s["paso"] == "CONFIRMAR_DIR":
            if inter_id == "dir_si":
                s["pedido"]["direccion"] = cliente.ultima_direccion
                return self._finalizar_orden(wa_id, s, cliente)
            s["paso"] = "PEDIR_DIR"
            return self.wa.enviar_texto(wa_id, "Dime la nueva dirección de entrega:")

        elif s["paso"] == "PEDIR_NOMBRE":
            s["pedido"]["nombre"] = texto
            s["paso"] = "PEDIR_DIR"
            return self.wa.enviar_texto(wa_id, f"Gracias {texto}. Ahora dime tu dirección completa:")

        elif s["paso"] == "PEDIR_DIR":
            s["pedido"]["direccion"] = texto
            self._guardar_cliente(wa_id, s["pedido"].get("nombre"), texto)
            return self._finalizar_orden(wa_id, s, cliente)

    # --- FUNCIONES DE APOYO ---
    def _enviar_lista_ingredientes(self, wa_id, s):
        rows = [{"id": f"ing_{i}", "title": ing} for i, ing in enumerate(INGREDIENTES)]
        return self.wa.enviar_lista(wa_id, "Ingredientes", "Selecciona tus ingredientes (3 incluidos):", "Mesa Code Pizza", "Ver Lista", [{"title": "Ingredientes", "rows": rows}])

    def _pasar_a_extras(self, wa_id, s):
        s["paso"] = "EXTRAS"
        rows = [{"id": k, "title": k.capitalize(), "description": f"${v}"} for k, v in MENU_EXTRAS.items()]
        return self.wa.enviar_lista(wa_id, "Extras", "¿Gustas algún extra?", "Mesa Code Pizza", "Ver Extras", [{"title": "Complementos", "rows": rows}])

    def _preguntar_entrega(self, wa_id, s, cliente):
        s["paso"] = "TIPO_ENTREGA"
        return self.wa.enviar_botones(wa_id, "¿Es a domicilio o recoges en local?", [{"id":"dom","title":"🛵 Domicilio"},{"id":"rec","title":"🛍️ Recoger"}])

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

        ticket = f"🧾 *TICKET #{p.id}*\n🍕 Pizza {s['pedido']['tamano'].capitalize()}\n🧀 Ing: {', '.join(s['pedido']['ingredientes'])}\n🥤 Ext: {', '.join(s['pedido']['extras'])}\n💰 *TOTAL: ${s['total']}*\n⏳ Tiempo: *40 min*."
        sesiones.pop(wa_id)
        return self.wa.enviar_texto(wa_id, ticket)