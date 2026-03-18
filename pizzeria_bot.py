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
        if wa_id.startswith("521"): wa_id = "52" + wa_id[3:]
        
        cliente = Cliente.query.filter_by(telefono=wa_id).first()
        if not cliente:
            cliente = Cliente(telefono=wa_id)
            db.session.add(cliente)
            db.session.commit()

        # Reset al escribir HOLA
        if texto.lower() == "hola":
            cliente.paso_actual = "MENU_PRINCIPAL"
            cliente.pedido_temporal = json.dumps({"ingredientes": [], "extras": [], "total": 0})
            db.session.commit()
            return self._enviar_menu_principal(wa_id, cliente)

        paso = cliente.paso_actual
        pedido = json.loads(cliente.pedido_temporal)

        # --- LÓGICA DE ESTADOS (Uso de elif para evitar cascada) ---

        if paso == "MENU_PRINCIPAL":
            if inter_id == "cat_pizzas":
                cliente.paso_actual = "PIZZA_TAMANO"
                db.session.commit()
                return self._enviar_tamanos(wa_id)
            elif inter_id in MENU_EXTRAS:
                pedido["extras"].append(inter_id)
                pedido["total"] += MENU_EXTRAS[inter_id]
                cliente.pedido_temporal = json.dumps(pedido)
                db.session.commit()
                return self.wa.enviar_botones(wa_id, f"✅ *{inter_id.capitalize()}* añadido. ¿Deseas algo más?", 
                                           [{"id":"hola","title":"Ver Menú"},{"id":"pagar","title":"💳 Finalizar pedido"}])

        elif paso == "PIZZA_TAMANO":
            if inter_id in MENU_PIZZAS:
                pedido["tamano"] = inter_id
                pedido["total"] += MENU_PIZZAS[inter_id]
                cliente.paso_actual = "PIZZA_INGREDIENTES"
                cliente.pedido_temporal = json.dumps(pedido)
                db.session.commit()
                return self._enviar_ingredientes(wa_id, "Elige tu primer ingrediente (3 incluidos):")

        elif paso == "PIZZA_INGREDIENTES":
            if inter_id == "fin_ing":
                cliente.paso_actual = "MENU_PRINCIPAL"
                db.session.commit()
                return self.wa.enviar_botones(wa_id, "🍕 Pizza lista. ¿Algo más del menú o prefieres pagar?", 
                                           [{"id":"hola","title":"🥤 Ver Extras"},{"id":"pagar","title":"💳 Pagar ahora"}])
            
            if inter_id and inter_id.startswith("ing_"):
                idx = int(inter_id.split("_")[1])
                ing = INGREDIENTES[idx]
                if ing not in pedido["ingredientes"]:
                    pedido["ingredientes"].append(ing)
                    if len(pedido["ingredientes"]) > 3: 
                        pedido["total"] += 20 # Costo extra
                
                cliente.pedido_temporal = json.dumps(pedido)
                db.session.commit()
                
                cant = len(pedido["ingredientes"])
                msg = f"✅ *{ing}* añadido ({cant}/3 gratis). ¿Deseas otro o terminamos con la pizza?"
                return self.wa.enviar_botones(wa_id, msg, [{"id":"otro_ing","title":"➕ Otro"},{"id":"fin_ing","title":"🏁 Terminar pizza"}])
            
            if texto == "➕ Otro":
                return self._enviar_ingredientes(wa_id, "Selecciona el siguiente ingrediente:")

        # Lógica de Entrega y Dirección
        if inter_id == "pagar" or texto.lower() == "pagar":
            cliente.paso_actual = "ENTREGA"
            db.session.commit()
            return self.wa.enviar_botones(wa_id, "¿Cómo deseas recibir tu pedido?", [{"id":"dom","title":"🛵 Domicilio"},{"id":"rec","title":"🛍️ Recoger"}])

        elif paso == "ENTREGA":
            pedido["tipo_entrega"] = "domicilio" if inter_id == "dom" else "recoger"
            cliente.pedido_temporal = json.dumps(pedido)
            if inter_id == "rec": return self._finalizar_pedido(wa_id, cliente, pedido)
            
            if cliente.ultima_direccion:
                cliente.paso_actual = "CONFIRMAR_DIR"
                db.session.commit()
                return self.wa.enviar_botones(wa_id, f"📍 ¿Enviamos a tu dirección anterior?\n_{cliente.ultima_direccion}_", 
                                           [{"id":"si_dir","title":"✅ Sí"},{"id":"no_dir","title":"✏️ Otra"}])
            
            cliente.paso_actual = "NOMBRE"
            db.session.commit()
            return self.wa.enviar_texto(wa_id, "Para el envío, ¿cuál es tu nombre?")

        elif paso == "CONFIRMAR_DIR":
            if inter_id == "si_dir":
                pedido["direccion"] = cliente.ultima_direccion
                return self._finalizar_pedido(wa_id, cliente, pedido)
            cliente.paso_actual = "DIRECCION"
            db.session.commit()
            return self.wa.enviar_texto(wa_id, "Escribe la nueva dirección completa:")

        elif paso == "NOMBRE":
            cliente.nombre = texto
            cliente.paso_actual = "DIRECCION"
            db.session.commit()
            return self.wa.enviar_texto(wa_id, "Ahora dime tu dirección (Calle y Número):")

        elif paso == "DIRECCION":
            cliente.ultima_direccion = texto
            pedido["direccion"] = texto
            db.session.commit()
            return self._finalizar_pedido(wa_id, cliente, pedido)

    # --- MÉTODOS DE MENSAJERÍA ---
    def _enviar_menu_principal(self, wa_id, cliente):
        nombre = cliente.nombre if cliente.nombre else "amigo"
        header = "🍕 MESA CODE PIZZA"
        body = f"¡Hola {nombre}! ¿Qué se te antoja hoy?\n\nSelecciona una categoría o un extra directamente:"
        sections = [
            {"title": "Pizzas", "rows": [{"id":"cat_pizzas", "title":"🍕 Ver Pizzas", "description":"Familiar, Mediana o Chica"}]},
            {"title": "Bebidas y Extras", "rows": [{"id":k, "title":k.capitalize(), "description":f"${v}"} for k,v in MENU_EXTRAS.items()]}
        ]
        return self.wa.enviar_lista(wa_id, header, body, "Mesa Code", "Ver Menú", sections)

    def _enviar_tamanos(self, wa_id):
        rows = [{"id": k, "title": k.capitalize(), "description": f"${v}"} for k, v in MENU_PIZZAS.items()]
        return self.wa.enviar_lista(wa_id, "Tamaños", "Elige el tamaño de tu pizza:", "Mesa Code", "Seleccionar", [{"title":"Opciones", "rows":rows}])

    def _enviar_ingredientes(self, wa_id, body):
        rows = [{"id": f"ing_{i}", "title": ing} for i, ing in enumerate(INGREDIENTES)]
        return self.wa.enviar_lista(wa_id, "Ingredientes", body, "3 incluidos, extra $20", "Ver Lista", [{"title":"Ingredientes", "rows":rows}])

    def _finalizar_pedido(self, wa_id, cliente, pedido):
        p = Pedido(cliente_id=cliente.id, total=pedido["total"], detalles_json=json.dumps(pedido), tipo_entrega=pedido["tipo_entrega"])
        db.session.add(p)
        cliente.paso_actual = "INICIO"
        db.session.commit()
        
        ticket = f"🧾 *ORDEN #{p.id}*\n"
        if pedido.get("tamano"): ticket += f"🍕 Pizza {pedido['tamano'].capitalize()}\n"
        if pedido.get("ingredientes"): ticket += f"🧀 Ing: {', '.join(pedido['ingredientes'])}\n"
        if pedido.get("extras"): ticket += f"🥤 Ext: {', '.join(pedido['extras'])}\n"
        ticket += f"💰 *TOTAL: ${pedido['total']}*\n⏳ Espera: *40 min*.\n¡Gracias!"
        return self.wa.enviar_texto(wa_id, ticket)