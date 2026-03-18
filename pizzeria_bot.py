from models import db, Cliente, Pedido
import json

# --- DATA ---
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
            cliente.pedido_temporal = json.dumps({"ingredientes": [], "extras": [], "total": 0, "pizzas": []})
            db.session.commit()
            return self._enviar_menu_principal(wa_id, cliente)

        paso = cliente.paso_actual
        pedido = json.loads(cliente.pedido_temporal)

        # --- MAQUINA DE ESTADOS ---

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
                return self.wa.enviar_botones(wa_id, f"✅ *{inter_id.capitalize()}* añadido. ¿Deseas algo más?", [{"id":"hola","title":"Ver Menú"},{"id":"pagar","title":"💳 Pagar ahora"}])

        elif paso == "PIZZA_TAMANO":
            if inter_id in MENU_PIZZAS:
                pedido["tamano_actual"] = inter_id
                pedido["total"] += MENU_PIZZAS[inter_id]
                cliente.paso_actual = "PIZZA_INGREDIENTES"
                cliente.pedido_temporal = json.dumps(pedido)
                db.session.commit()
                return self._enviar_lista_ingredientes(wa_id, "Elige tu 1er ingrediente (3 incluidos):")

        elif paso == "PIZZA_INGREDIENTES":
            if inter_id == "fin_ing":
                cliente.paso_actual = "MENU_PRINCIPAL"
                db.session.commit()
                return self.wa.enviar_botones(wa_id, "🍕 Pizza configurada. ¿Deseas agregar extras o finalizar?", [{"id":"hola","title":"🥤 Ver Extras"},{"id":"pagar","title":"💳 Finalizar"}])
            
            if inter_id and inter_id.startswith("ing_"):
                idx = int(inter_id.split("_")[1])
                ing = INGREDIENTES[idx]
                if ing not in pedido["ingredientes"]:
                    pedido["ingredientes"].append(ing)
                    if len(pedido["ingredientes"]) > 3: pedido["total"] += 20
                
                cliente.pedido_temporal = json.dumps(pedido)
                db.session.commit()
                
                cant = len(pedido["ingredientes"])
                msg = f"✅ *{ing}* listo ({cant}/3 gratis). ¿Otro ingrediente o terminamos?"
                return self.wa.enviar_botones(wa_id, msg, [{"id":"otro_ing","title":"➕ Otro"},{"id":"fin_ing","title":"🏁 Terminar"}])
            
            if texto == "➕ Otro":
                return self._enviar_lista_ingredientes(wa_id, "Elige el siguiente ingrediente:")

        # Lógica de Pago / Entrega
        if inter_id == "pagar" or texto.lower() == "pagar":
            cliente.paso_actual = "TIPO_ENTREGA"
            db.session.commit()
            return self.wa.enviar_botones(wa_id, "¿Cómo deseas recibir tu pedido?", [{"id":"dom","title":"🛵 Domicilio"},{"id":"rec","title":"🛍️ Recoger"}])

        # ... (Aquí sigue la lógica de dirección que ya tenías)
        return self._manejar_entrega(wa_id, cliente, pedido, texto, inter_id)

    # --- MÉTODOS DE MENÚ ---
    def _enviar_menu_principal(self, wa_id, cliente):
        nombre = cliente.nombre if cliente.nombre else "amigo"
        header = "🍕 MESA CODE PIZZA"
        body = f"¡Hola {nombre}! ¿Qué se te antoja hoy?\n\nSelecciona una categoría o un extra directo:"
        sections = [
            {"title": "Plato Fuerte", "rows": [{"id":"cat_pizzas", "title":"🍕 Pizzas", "description":"Familiar, Mediana o Chica"}]},
            {"title": "Extras y Bebidas", "rows": [{"id":k, "title":k.capitalize(), "description":f"${v}"} for k,v in MENU_EXTRAS.items()]}
        ]
        return self.wa.enviar_lista(wa_id, header, body, "Menú Completo", "Ver Menú", sections)

    def _enviar_tamanos(self, wa_id):
        rows = [{"id": k, "title": k.capitalize(), "description": f"${v}"} for k, v in MENU_PIZZAS.items()]
        return self.wa.enviar_lista(wa_id, "Tamaños", "Selecciona el tamaño de tu pizza:", "Mesa Code", "Ver Tamaños", [{"title":"Opciones", "rows":rows}])

    def _enviar_lista_ingredientes(self, wa_id, body):
        rows = [{"id": f"ing_{i}", "title": ing} for i, ing in enumerate(INGREDIENTES)]
        return self.wa.enviar_lista(wa_id, "Ingredientes", body, "3 incluidos, extra $20", "Seleccionar", [{"title":"Lista", "rows":rows}])

    def _manejar_entrega(self, wa_id, cliente, pedido, texto, inter_id):
        # (Lógica simplificada de dirección para asegurar el funcionamiento)
        if cliente.paso_actual == "TIPO_ENTREGA":
            pedido["entrega"] = "domicilio" if inter_id == "dom" else "recoger"
            cliente.pedido_temporal = json.dumps(pedido)
            if inter_id == "rec": return self._finalizar(wa_id, cliente, pedido)
            cliente.paso_actual = "PEDIR_DIR"
            db.session.commit()
            return self.wa.enviar_texto(wa_id, "Dime tu dirección completa para el envío:")
        
        elif cliente.paso_actual == "PEDIR_DIR":
            pedido["direccion"] = texto
            cliente.ultima_direccion = texto
            db.session.commit()
            return self._finalizar(wa_id, cliente, pedido)

    def _finalizar(self, wa_id, cliente, pedido):
        p = Pedido(cliente_id=cliente.id, total=pedido["total"], detalles_json=json.dumps(pedido), tipo_entrega=pedido["entrega"])
        db.session.add(p)
        cliente.paso_actual = "INICIO"
        db.session.commit()
        ticket = f"🧾 *ORDEN #{p.id}*\nTotal: ${pedido['total']}\nEspera: 40 min."
        return self.wa.enviar_texto(wa_id, ticket)