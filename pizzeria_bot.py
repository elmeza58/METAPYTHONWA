# ~/Documents/APIMETAPYTHON/pizzeria_bot.py
from models import db, Cliente, Pedido
import json

# --- CONFIGURACIÓN DEL MENÚ MR. BIGO'S ---
MENU_PIZZAS = {
    "familiar": 170, 
    "grande": 150, 
    "mediana": 130,
    "promo_pepperoni": 99 # Pizza Grande de Pepperoni
}

MENU_COMBOS = {
    "combo_grande": 300, # 2 Grandes + Ensalada + Soda 2L
    "combo_familiar": 370 # 2 Familiares + Espaguetti + Soda 2L
}

MENU_SNACKS = {
    "ensalada": 65,
    "espaguetti": 85,
    "crazy_papas": 85,
    "boneless": 120,
    "alitas": 130,
    "boneless_grande": 210,
    "boneless_familiar": 250
}

# Ingredientes actualizados del volante
INGREDIENTES_PROT = ["Jamón", "Salami", "Pepperoni", "Tocino", "Chorizo", "Salchicha", "Chilorio", "Machaca"]
INGREDIENTES_VEG = ["Champiñón", "Pimiento Verde", "Aceituna Negra", "Cebolla Blanca", "Elote", "Jalapeño", "Frijol", "Piña", "Cereza", "Chile Verde"]

class PizzeriaBot:
    def __init__(self, config, wa_service):
        self.wa = wa_service
        self.config = config

    def gestionar_pedido(self, wa_id, texto, inter_id=None):
        """Maneja el flujo de pedidos basado en el menú de Mr. Bigo's."""
        if wa_id.startswith("521"): wa_id = "52" + wa_id[3:]
        
        cliente = Cliente.query.filter_by(telefono=wa_id).first()
        if not cliente:
            cliente = Cliente(telefono=wa_id, paso_actual="INICIO")
            db.session.add(cliente)
            db.session.commit()

        # --- REINICIO O NAVEGACIÓN ---
        if (texto.lower() == "hola" and inter_id is None) or inter_id == "hola":
            cliente.paso_actual = "MENU_PRINCIPAL"
            # Ahora el total incluye 5 ingredientes gratis
            cliente.pedido_temporal = json.dumps({"ingredientes": [], "extras": [], "total": 0})
            db.session.commit()
            return self._enviar_menu_principal(wa_id, cliente)

        paso = cliente.paso_actual
        pedido = json.loads(cliente.pedido_temporal)

        # --- MÁQUINA DE ESTADOS ---
        
        # 1. MENÚ PRINCIPAL (Categorías del Volante)
        if paso == "MENU_PRINCIPAL":
            if inter_id == "cat_pizzas":
                cliente.paso_actual = "PIZZA_TAMANO"
                db.session.commit()
                return self._enviar_tamanos(wa_id)
            
            elif inter_id == "cat_combos":
                cliente.paso_actual = "COMBOS"
                db.session.commit()
                return self._enviar_combos(wa_id)
            
            elif inter_id == "cat_snacks":
                cliente.paso_actual = "SNACKS"
                db.session.commit()
                return self._enviar_snacks(wa_id)

        # 2. SELECCIÓN DE COMBOS
        elif paso == "COMBOS":
            if inter_id in MENU_COMBOS:
                pedido["extras"].append(inter_id)
                pedido["total"] += MENU_COMBOS[inter_id]
                cliente.pedido_temporal = json.dumps(pedido)
                db.session.commit()
                resumen = f"✅ *{inter_id.replace('_', ' ').capitalize()}* añadido.\nTotal: *${pedido['total']}*"
                return self.wa.enviar_botones(wa_id, resumen, [{"id":"hola","title":"🥤 Ver Menú"},{"id":"pagar","title":"💳 Pagar"}])

        # 3. SELECCIÓN DE SNACKS
        elif paso == "SNACKS":
            if inter_id in MENU_SNACKS:
                pedido["extras"].append(inter_id)
                pedido["total"] += MENU_SNACKS[inter_id]
                cliente.pedido_temporal = json.dumps(pedido)
                db.session.commit()
                resumen = f"✅ *{inter_id.capitalize()}* añadido.\nTotal: *${pedido['total']}*"
                return self.wa.enviar_botones(wa_id, resumen, [{"id":"hola","title":"🥤 Ver Menú"},{"id":"pagar","title":"💳 Pagar"}])

        # 4. TAMAÑO DE PIZZA
        elif paso == "PIZZA_TAMANO":
            if inter_id in MENU_PIZZAS:
                pedido["tamano"] = inter_id
                pedido["total"] += MENU_PIZZAS[inter_id]
                # Si es la promo de pepperoni, saltamos ingredientes
                if inter_id == "promo_pepperoni":
                    pedido["ingredientes"] = ["Pepperoni"]
                    cliente.paso_actual = "MENU_PRINCIPAL"
                    cliente.pedido_temporal = json.dumps(pedido)
                    db.session.commit()
                    return self.wa.enviar_botones(wa_id, "✅ Promo Pepperoni añadida. ¿Algo más?", [{"id":"hola","title":"🥤 Ver Menú"},{"id":"pagar","title":"💳 Pagar"}])
                
                cliente.paso_actual = "PIZZA_INGREDIENTES"
                cliente.pedido_temporal = json.dumps(pedido)
                db.session.commit()
                return self.wa.enviar_botones(wa_id, f"Elegiste Pizza {inter_id.capitalize()}.\nEsta pizza incluye *hasta 5 ingredientes*.\n¿De qué categoría prefieres?", 
                                           [{"id":"cat_prot","title":"🥩 Proteínas"},{"id":"cat_veg","title":"🌿 Vegetales"}])

        # 5. INGREDIENTES (Lógica de 5 incluidos)
        elif paso == "PIZZA_INGREDIENTES":
            if inter_id == "cat_prot":
                return self._enviar_ingredientes(wa_id, INGREDIENTES_PROT, "Proteínas", "prot")
            elif inter_id == "cat_veg":
                return self._enviar_ingredientes(wa_id, INGREDIENTES_VEG, "Vegetales", "veg")
            elif inter_id == "fin_ing":
                cliente.paso_actual = "MENU_PRINCIPAL"
                db.session.commit()
                return self.wa.enviar_botones(wa_id, "🍕 Pizza personalizada. ¿Deseas agregar snacks o pagar?", [{"id":"hola","title":"🥤 Ver Menú"},{"id":"pagar","title":"💳 Pagar"}])
            
            elif inter_id and ("_prot_" in inter_id or "_veg_" in inter_id):
                tipo, idx = inter_id.split("_")[1], int(inter_id.split("_")[2])
                ing = INGREDIENTES_PROT[idx] if tipo == "prot" else INGREDIENTES_VEG[idx]
                
                if ing not in pedido["ingredientes"]:
                    pedido["ingredientes"].append(ing)
                    # Cobro extra solo después del 5to ingrediente
                    if len(pedido["ingredientes"]) > 5: pedido["total"] += 20
                
                cliente.pedido_temporal = json.dumps(pedido)
                db.session.commit()
                
                cant = len(pedido["ingredientes"])
                msg = f"✅ *{ing}* añadido ({cant}/5 incluidos).\n¿Deseas otro ingrediente o terminar?"
                return self.wa.enviar_botones(wa_id, msg, [{"id":"cat_prot","title":"🥩 Proteínas"},{"id":"cat_veg","title":"🌿 Vegetales"},{"id":"fin_ing","title":"🏁 Terminar"}])

        # 6. FINALIZACIÓN (PAGO Y ENTREGA)
        if inter_id == "pagar":
            cliente.paso_actual = "ENTREGA"
            db.session.commit()
            return self.wa.enviar_botones(wa_id, f"El total de tu orden es: *${pedido['total']}*\n¿Cómo deseas recibirlo?", 
                                       [{"id":"dom","title":"🛵 Domicilio"},{"id":"rec","title":"🛍️ Recoger"}])

        elif paso == "ENTREGA":
            pedido["tipo_entrega"] = "domicilio" if inter_id == "dom" else "recoger"
            cliente.pedido_temporal = json.dumps(pedido)
            if inter_id == "rec": return self._finalizar_orden(wa_id, cliente, pedido)
            
            cliente.paso_actual = "DIRECCION"
            db.session.commit()
            return self.wa.enviar_texto(wa_id, "📍 Por favor, escribe tu dirección completa para el envío:")

        elif paso == "DIRECCION":
            pedido["direccion"] = texto
            cliente.ultima_direccion = texto
            db.session.commit()
            return self._finalizar_orden(wa_id, cliente, pedido)

    # --- FUNCIONES AUXILIARES DE MENÚ ---
    def _enviar_menu_principal(self, wa_id, cliente):
        nombre = cliente.nombre if cliente.nombre else "amigo"
        sections = [
            {"title": "💎 Promociones", "rows": [
                {"id":"cat_combos", "title":"🔥 Ver Combos", "description":"2 Pizzas + Extra + Soda"},
                {"id":"promo_pepperoni", "title":"🍕 Pepperoni Grande $99", "description":"¡Precio especial!"}
            ]},
            {"title": "🍕 Arma tu Pizza", "rows": [
                {"id":"cat_pizzas", "title":"Pizzas Individuales", "description":"Familiar, Grande o Mediana"}
            ]},
            {"title": "🍗 Snacks y Extras", "rows": [
                {"id":"cat_snacks", "title":"Ver Snacks", "description":"Alitas, Boneless, Papas y más"}
            ]}
        ]
        return self.wa.enviar_lista(wa_id, "Mr. Bigo's Pizza", f"¡Hola {nombre}! Bienvenido.\n\n¿Qué se te antoja de nuestro menú hoy?", "Menú Principal", "Ver Opciones", sections)

    def _enviar_combos(self, wa_id):
        rows = [{"id": k, "title": k.replace('_', ' ').capitalize(), "description": f"${v}"} for k, v in MENU_COMBOS.items()]
        return self.wa.enviar_lista(wa_id, "Combos Bigo's", "Selecciona tu combo favorito:", "Mr. Bigo's", "Ver Combos", [{"title":"Paquetes", "rows":rows}])

    def _enviar_snacks(self, wa_id):
        rows = [{"id": k, "title": k.replace('_', ' ').capitalize(), "description": f"${v}"} for k, v in MENU_SNACKS.items()]
        return self.wa.enviar_lista(wa_id, "Snacks", "Nuestros acompañamientos:", "Mr. Bigo's", "Ver Snacks", [{"title":"Extras", "rows":rows}])

    def _enviar_tamanos(self, wa_id):
        # Excluimos la promo de 99 para no duplicar
        pizzas_std = {k: v for k, v in MENU_PIZZAS.items() if k != "promo_pepperoni"}
        rows = [{"id": k, "title": k.capitalize(), "description": f"${v}"} for k, v in pizzas_std.items()]
        return self.wa.enviar_lista(wa_id, "Tamaños", "Elige el tamaño de tu pizza:", "Hasta 5 ingredientes", "Seleccionar", [{"title":"Pizzas", "rows":rows}])

    def _enviar_ingredientes(self, wa_id, lista, nombre_cat, prefijo):
        rows = [{"id": f"ing_{prefijo}_{i}", "title": ing} for i, ing in enumerate(lista)]
        return self.wa.enviar_lista(wa_id, f"Lista: {nombre_cat}", "Selecciona un ingrediente:", "Mr. Bigo's", "Ver Lista", [{"title":nombre_cat, "rows":rows}])

    def _finalizar_orden(self, wa_id, cliente, pedido):
        p = Pedido(cliente_id=cliente.id, total=pedido["total"], detalles_json=json.dumps(pedido), tipo_entrega=pedido["tipo_entrega"])
        db.session.add(p)
        cliente.paso_actual = "INICIO"
        db.session.commit()
        
        ticket = f"🧾 *ORDEN MR. BIGO'S #{p.id}*\n"
        ticket += f"━━━━━━━━━━━━━━\n"
        if "tamano" in pedido: ticket += f"🍕 Pizza {pedido['tamano'].capitalize()}\n"
        if pedido["ingredientes"]: ticket += f"🧀 Ing: {', '.join(pedido['ingredientes'])}\n"
        if pedido["extras"]: ticket += f"🥤 Items: {', '.join([x.replace('_', ' ') for x in pedido['extras']])}\n"
        ticket += f"📍 Entrega: {pedido['tipo_entrega'].capitalize()}\n"
        ticket += f"💰 *TOTAL: ${pedido['total']}*\n"
        ticket += f"━━━━━━━━━━━━━━\n"
        ticket += "⏳ Tiempo estimado: *40 min*.\n¡Gracias por tu pedido! 🍕🔥"
        return self.wa.enviar_texto(wa_id, ticket)