# ~/Documents/APIMETAPYTHON/pizzeria_bot.py
from models import db, Cliente, Pedido
import json

MENU_PIZZAS = {"familiar": 150, "mediana": 130, "chica": 80}
MENU_EXTRAS = {"spagguetti": 80, "ensalada": 60, "queso": 100, "soda": 50}
INGREDIENTES = [
    "Jamón", "Salami", "Peperoni", "Tocino", "Machaca", "Jalapeño", 
    "Aceituna", "Atún", "Salchicha", "Champiñones", "Pimientos", 
    "Tomate", "Chorizo", "Piña", "Elote", "Cereza", "Chilorio", "Cebolla"
]

class PizzeriaBot:
    def __init__(self, config, wa_service):
        self.wa = wa_service
        self.config = config

    def gestionar_mensaje(self, wa_id, texto, inter_id=None):
        # 1. Normalización de número de México
        if wa_id.startswith("521"): wa_id = "52" + wa_id[3:]
        
        # 2. Obtener cliente de la DB (o crear uno nuevo)
        cliente = Cliente.query.filter_by(telefono=wa_id).first()
        if not cliente:
            cliente = Cliente(telefono=wa_id)
            db.session.add(cliente)
            db.session.commit()

        # 3. Resetear si escribe 'Hola'
        if texto.lower() == "hola":
            cliente.paso_actual = "INICIO"
            cliente.pedido_temporal = json.dumps({"ingredientes": [], "extras": [], "total": 0})
            db.session.commit()

        # 4. Cargar datos de la sesión desde la DB
        paso = cliente.paso_actual
        pedido_temp = json.loads(cliente.pedido_temporal)

        # --- FLUJO DE ESTADOS ---

        # ESTADO 1: BIENVENIDA
        if paso == "INICIO":
            cliente.paso_actual = "TAMAÑO"
            db.session.commit()
            
            nombre = cliente.nombre if cliente.nombre else "amigo"
            saludo = f"🍕 ¡Hola *{nombre}*! Bienvenido a Mesa Code Pizza.\n\n¿Qué tamaño de pizza te gustaría ordenar?"
            rows = [{"id": k, "title": k.capitalize(), "description": f"${v}"} for k, v in MENU_PIZZAS.items()]
            return self.wa.enviar_lista(wa_id, "Menú", saludo, "Elige uno:", "Ver Tamaños", [{"title": "Pizzas", "rows": rows}])

        # ESTADO 2: SELECCIÓN DE TAMAÑO
        elif paso == "TAMAÑO":
            if not inter_id or inter_id not in MENU_PIZZAS:
                return self.wa.enviar_texto(wa_id, "⚠️ Selecciona un tamaño de la lista.")
            
            pedido_temp["tamano"] = inter_id
            pedido_temp["total"] = MENU_PIZZAS[inter_id]
            
            cliente.paso_actual = "INGREDIENTES"
            cliente.pedido_temporal = json.dumps(pedido_temp)
            db.session.commit()
            
            return self._enviar_lista_ingredientes(wa_id)

        # ESTADO 3: INGREDIENTES
        elif paso == "INGREDIENTES":
            if inter_id == "fin_ing":
                return self._pasar_a_extras(wa_id, cliente, pedido_temp)
            
            if inter_id and inter_id.startswith("ing_"):
                idx = int(inter_id.split("_")[1])
                ing = INGREDIENTES[idx]
                
                if ing not in pedido_temp["ingredientes"]:
                    pedido_temp["ingredientes"].append(ing)
                    if len(pedido_temp["ingredientes"]) > 3:
                        pedido_temp["total"] += 20 # Extra
                
                cliente.pedido_temporal = json.dumps(pedido_temp)
                db.session.commit()
                
                cant = len(pedido_temp["ingredientes"])
                body = f"✅ *{ing}* añadido ({cant}/3 gratis).\n\n¿Deseas otro o pasar a los extras?"
                buttons = [{"id":"fin_ing","title":"🏁 Finalizar"}, {"id":"seguir_ing","title":"➕ Otro"}]
                return self.wa.enviar_botones(wa_id, body, buttons)
            
            if texto == "➕ Otro":
                return self._enviar_lista_ingredientes(wa_id)

        # ESTADO 4: EXTRAS
        elif paso == "EXTRAS":
            if inter_id == "fin_ext":
                return self._preguntar_entrega(wa_id, cliente)
            
            if inter_id in MENU_EXTRAS:
                pedido_temp["extras"].append(inter_id)
                pedido_temp["total"] += MENU_EXTRAS[inter_id]
                cliente.pedido_temporal = json.dumps(pedido_temp)
                db.session.commit()
                
                return self.wa.enviar_botones(wa_id, f"✅ {inter_id.capitalize()} añadido. ¿Algo más?", 
                                           [{"id":"fin_ext","title":"🏁 Finalizar"}, {"id":"mas_ext","title":"🥤 Ver Extras"}])
            return self._pasar_a_extras(wa_id, cliente, pedido_temp)

        # ESTADO 5: ENTREGA
        elif paso == "TIPO_ENTREGA":
            pedido_temp["entrega"] = "domicilio" if inter_id == "dom" else "recoger"
            cliente.pedido_temporal = json.dumps(pedido_temp)
            
            if inter_id == "rec": 
                return self._finalizar_orden(wa_id, cliente, pedido_temp)
            
            if cliente.ultima_direccion:
                cliente.paso_actual = "CONFIRMAR_DIR"
                db.session.commit()
                msg = f"📍 ¿Enviamos a tu dirección anterior?\n_{cliente.ultima_direccion}_"
                return self.wa.enviar_botones(wa_id, msg, [{"id":"dir_si","title":"✅ Sí"},{"id":"dir_no","title":"✏️ Otra"}])
            
            cliente.paso_actual = "PEDIR_NOMBRE"
            db.session.commit()
            return self.wa.enviar_texto(wa_id, "¿Cuál es tu nombre?")

        # ESTADOS DE DIRECCIÓN
        elif paso == "CONFIRMAR_DIR":
            if inter_id == "dir_si":
                pedido_temp["direccion"] = cliente.ultima_direccion
                return self._finalizar_orden(wa_id, cliente, pedido_temp)
            cliente.paso_actual = "PEDIR_DIR"
            db.session.commit()
            return self.wa.enviar_texto(wa_id, "Escribe la dirección de entrega:")

        elif paso == "PEDIR_NOMBRE":
            cliente.nombre = texto
            cliente.paso_actual = "PEDIR_DIR"
            db.session.commit()
            return self.wa.enviar_texto(wa_id, "Dime tu dirección completa:")

        elif paso == "PEDIR_DIR":
            cliente.ultima_direccion = texto
            pedido_temp["direccion"] = texto
            db.session.commit()
            return self._finalizar_orden(wa_id, cliente, pedido_temp)

    # --- MÉTODOS DE APOYO ---
    def _enviar_lista_ingredientes(self, wa_id):
        rows = [{"id": f"ing_{i}", "title": ing} for i, ing in enumerate(INGREDIENTES)]
        return self.wa.enviar_lista(wa_id, "Ingredientes", "Selecciona tus ingredientes:", "Mesa Code", "Ver Lista", [{"title": "Opciones", "rows": rows}])

    def _pasar_a_extras(self, wa_id, cliente, pedido_temp):
        cliente.paso_actual = "EXTRAS"
        db.session.commit()
        rows = [{"id": k, "title": k.capitalize(), "description": f"${v}"} for k, v in MENU_EXTRAS.items()]
        return self.wa.enviar_lista(wa_id, "Extras", "¿Gustas algún extra?", "Mesa Code", "Ver Extras", [{"title": "Extras", "rows": rows}])

    def _preguntar_entrega(self, wa_id, cliente):
        cliente.paso_actual = "TIPO_ENTREGA"
        db.session.commit()
        return self.wa.enviar_botones(wa_id, "¿Es a domicilio o recoges?", [{"id":"dom","title":"🛵 Domicilio"},{"id":"rec","title":"🛍️ Recoger"}])

    def _finalizar_orden(self, wa_id, cliente, pedido_temp):
        p = Pedido(cliente_id=cliente.id, total=pedido_temp["total"], detalles_json=json.dumps(pedido_temp), tipo_entrega=pedido_temp["entrega"])
        db.session.add(p)
        
        # Resetear cliente para el próximo pedido
        cliente.paso_actual = "INICIO"
        cliente.pedido_temporal = json.dumps({"ingredientes": [], "extras": [], "total": 0})
        db.session.commit()

        ticket = f"🧾 *ORDEN #{p.id}*\n🍕 Pizza {pedido_temp['tamano'].capitalize()}\n🧀 Ing: {', '.join(pedido_temp['ingredientes'])}\n💰 *TOTAL: ${pedido_temp['total']}*\n⏳ Tiempo: *40 min*."
        return self.wa.enviar_texto(wa_id, ticket)