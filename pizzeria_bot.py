# ~/Documents/APIMETAPYTHON/pizzeria_bot.py
from models import db, Cliente, Pedido
import json

# --- DATA DEL MENÚ MR. BIGO'S ---
MENU_PIZZAS = {"familiar": 170, "grande": 150, "mediana": 130, "promo_pepperoni": 99}
MENU_COMBOS = {"combo_grande": 300, "combo_familiar": 370}
MENU_SNACKS = {"ensalada": 65, "espaguetti": 85, "crazy_papas": 85, "boneless": 120, "alitas": 130}

# Diccionario de Especialidades con sus ingredientes
ESPECIALIDADES = {
    "Suprema": ["Salami", "Champiñón", "Pimiento verde", "Aceituna negra", "Cebolla blanca", "Pepperoni", "Elote"],
    "Mexicana": ["Tocino", "Chorizo", "Jalapeño", "Frijol"],
    "Carnes Frías": ["Jamón", "Salchicha", "Tocino", "Salami"],
    "Italiana": ["Salchicha", "Pepperoni", "Aceituna negra", "Champiñón", "Pimiento verde"],
    "Hawaiana": ["Jamón", "Cereza", "Piña"],
    "Culichi": ["Chilorio", "Champiñón", "Pimiento verde"],
    "Sonora": ["Machaca", "Cebolla cambray", "Chile verde"],
    "Bigo Express": ["Pepperoni"]
}

INGREDIENTES_PROT = ["Jamón", "Salami", "Pepperoni", "Tocino", "Chorizo", "Salchicha", "Chilorio", "Machaca"]
INGREDIENTES_VEG = ["Champiñón", "Pimiento Verde", "Aceituna Negra", "Cebolla Blanca", "Elote", "Jalapeño", "Frijol", "Piña", "Cereza", "Chile Verde"]

class PizzeriaBot:
    def __init__(self, config, wa_service):
        self.wa = wa_service
        self.config = config

    def gestionar_pedido(self, wa_id, texto, inter_id=None):
        if wa_id.startswith("521"): wa_id = "52" + wa_id[3:]
        
        cliente = Cliente.query.filter_by(telefono=wa_id).first()
        if not cliente:
            cliente = Cliente(telefono=wa_id, paso_actual="INICIO")
            db.session.add(cliente)
            db.session.commit()

        # --- NAVEGACIÓN ---
        if (texto.lower() == "hola" and inter_id is None) or inter_id == "hola":
            cliente.paso_actual = "MENU_PRINCIPAL"
            cliente.pedido_temporal = json.dumps({"pizzas": [], "extras": [], "total": 0})
            db.session.commit()
            return self._enviar_menu_principal(wa_id, cliente)

        paso = cliente.paso_actual
        pedido = json.loads(cliente.pedido_temporal)

        # --- MÁQUINA DE ESTADOS ---
        
        if paso == "MENU_PRINCIPAL":
            if inter_id == "cat_pizzas":
                cliente.paso_actual = "PIZZA_TAMANO"
                db.session.commit()
                return self._enviar_tamanos(wa_id)
            
            elif inter_id in MENU_COMBOS:
                pedido["total"] += MENU_COMBOS[inter_id]
                pedido["combo_activo"] = inter_id # Guardamos qué combo es
                pedido["pizzas_por_configurar"] = 2 # Los combos traen 2 pizzas
                cliente.paso_actual = "PIZZA_TIPO_ELECCION"
                cliente.pedido_temporal = json.dumps(pedido)
                db.session.commit()
                return self.wa.enviar_botones(wa_id, f"Elegiste el {inter_id.replace('_', ' ')}.\nConfiguremos la *Pizza 1*.\n¿Qué prefieres?", 
                                           [{"id":"tipo_esp","title":"🌟 Especialidad"},{"id":"tipo_ing","title":"👨‍🍳 Armarla"}])

            elif inter_id in MENU_SNACKS:
                pedido["extras"].append(inter_id)
                pedido["total"] += MENU_SNACKS[inter_id]
                cliente.pedido_temporal = json.dumps(pedido)
                db.session.commit()
                return self.wa.enviar_botones(wa_id, f"✅ *{inter_id.capitalize()}* añadido. ¿Algo más?", 
                                           [{"id":"hola","title":"🥤 Ver Menú"},{"id":"pagar","title":"💳 Pagar"}])

        elif paso == "PIZZA_TAMANO":
            if inter_id in MENU_PIZZAS:
                pedido["total"] += MENU_PIZZAS[inter_id]
                pedido["tamano_actual"] = inter_id
                pedido["pizzas_por_configurar"] = 1
                cliente.paso_actual = "PIZZA_TIPO_ELECCION"
                cliente.pedido_temporal = json.dumps(pedido)
                db.session.commit()
                return self.wa.enviar_botones(wa_id, f"Pizza {inter_id.capitalize()}.\n¿Quieres una especialidad o armarla tú mismo?", 
                                           [{"id":"tipo_esp","title":"🌟 Especialidad"},{"id":"tipo_ing","title":"👨‍🍳 Armarla"}])

        elif paso == "PIZZA_TIPO_ELECCION":
            if inter_id == "tipo_esp":
                return self._enviar_especialidades(wa_id)
            elif inter_id == "tipo_ing":
                cliente.paso_actual = "PIZZA_INGREDIENTES"
                db.session.commit()
                return self.wa.enviar_botones(wa_id, "Selecciona categoría:", [{"id":"cat_prot","title":"🥩 Proteínas"},{"id":"cat_veg","title":"🌿 Vegetales"}])

        elif paso == "PIZZA_ESPECIALIDAD":
            if inter_id.startswith("esp_"):
                nombre_esp = inter_id.split("_")[1].replace("_", " ").title()
                pedido["pizzas"].append({"nombre": nombre_esp, "ingredientes": ESPECIALIDADES[nombre_esp]})
                return self._verificar_siguiente_paso(wa_id, cliente, pedido)

        elif paso == "PIZZA_INGREDIENTES":
            if inter_id == "cat_prot": return self._enviar_ingredientes(wa_id, INGREDIENTES_PROT, "Proteínas", "prot")
            if inter_id == "cat_veg": return self._enviar_ingredientes(wa_id, INGREDIENTES_VEG, "Vegetales", "veg")
            
            if inter_id and ("_prot_" in inter_id or "_veg_" in inter_id):
                tipo, idx = inter_id.split("_")[1], int(inter_id.split("_")[2])
                ing = INGREDIENTES_PROT[idx] if tipo == "prot" else INGREDIENTES_VEG[idx]
                
                # Buscamos la pizza que estamos armando actualmente o creamos una
                if "armando" not in pedido: pedido["armando"] = []
                if ing not in pedido["armando"]:
                    pedido["armando"].append(ing)
                    if len(pedido["armando"]) > 5: pedido["total"] += 20
                
                cliente.pedido_temporal = json.dumps(pedido)
                db.session.commit()
                msg = f"✅ *{ing}* ({len(pedido['armando'])}/5 gratis). ¿Otro o terminamos esta pizza?"
                return self.wa.enviar_botones(wa_id, msg, [{"id":"cat_prot","title":"🥩 Proteínas"},{"id":"cat_veg","title":"🌿 Vegetales"},{"id":"fin_pizza","title":"🏁 Terminar"}])

            if inter_id == "fin_pizza":
                pedido["pizzas"].append({"nombre": "Personalizada", "ingredientes": pedido["armando"]})
                pedido.pop("armando")
                return self._verificar_siguiente_paso(wa_id, cliente, pedido)

        # --- PAGO ---
        if inter_id == "pagar":
            cliente.paso_actual = "ENTREGA"
            db.session.commit()
            return self.wa.enviar_botones(wa_id, f"Total: *${pedido['total']}*\n¿Cómo lo recibes?", [{"id":"dom","title":"🛵 Domicilio"},{"id":"rec","title":"🛍️ Recoger"}])

        elif paso == "ENTREGA":
            pedido["tipo_entrega"] = "domicilio" if inter_id == "dom" else "recoger"
            cliente.pedido_temporal = json.dumps(pedido)
            if inter_id == "rec": return self._finalizar_orden(wa_id, cliente, pedido)
            cliente.paso_actual = "DIRECCION"
            db.session.commit()
            return self.wa.enviar_texto(wa_id, "Escribe tu dirección:")

        elif paso == "DIRECCION":
            pedido["direccion"] = texto
            return self._finalizar_orden(wa_id, cliente, pedido)

    # --- FUNCIONES DE APOYO ---
    def _verificar_siguiente_paso(self, wa_id, cliente, pedido):
        pedido["pizzas_por_configurar"] -= 1
        if pedido["pizzas_por_configurar"] > 0:
            msg = f"¡Pizza 1 lista! Ahora configuremos la *Pizza 2* del combo.\n¿Qué prefieres?"
            cliente.paso_actual = "PIZZA_TIPO_ELECCION"
            cliente.pedido_temporal = json.dumps(pedido)
            db.session.commit()
            return self.wa.enviar_botones(wa_id, msg, [{"id":"tipo_esp","title":"🌟 Especialidad"},{"id":"tipo_ing","title":"👨‍🍳 Armarla"}])
        else:
            cliente.paso_actual = "MENU_PRINCIPAL"
            cliente.pedido_temporal = json.dumps(pedido)
            db.session.commit()
            return self.wa.enviar_botones(wa_id, "✅ Pizzas configuradas. ¿Deseas agregar snacks o pagar?", [{"id":"hola","title":"🥤 Ver Menú"},{"id":"pagar","title":"💳 Pagar"}])

    def _enviar_menu_principal(self, wa_id, cliente):
        sections = [
            {"title": "Pizzas y Combos", "rows": [
                {"id":"cat_pizzas", "title":"🍕 Arma tu Pizza", "description":"Individual: Familiar, Grande, Mediana"},
                {"id":"combo_grande", "title":"🎁 Combo Grande $300", "description":"2 Grandes + Ensalada + Soda"},
                {"id":"combo_familiar", "title":"🎁 Combo Familiar $370", "description":"2 Fam + Espaguetti + Soda"}
            ]},
            {"title": "Snacks", "rows": [{"id":k, "title":k.capitalize(), "description":f"${v}"} for k,v in MENU_SNACKS.items()]}
        ]
        return self.wa.enviar_lista(wa_id, "Mr. Bigo's Pizza", "¡Bienvenido! Elige una opción:", "Menú", "Ver Opciones", sections)

    # ~/Documents/APIMETAPYTHON/pizzeria_bot.py

    def _enviar_especialidades(self, wa_id):
        cliente = Cliente.query.filter_by(telefono=wa_id).first()
        cliente.paso_actual = "PIZZA_ESPECIALIDAD"
        db.session.commit()
        
        rows = []
        for k, v in ESPECIALIDADES.items():
            # Creamos la descripción con los ingredientes
            desc = ", ".join(v)
            # ⚠️ REGLA DE META: Máximo 72 caracteres. Recortamos a 69 + "..." si es necesario.
            if len(desc) > 72:
                desc = desc[:69] + "..."
                
            rows.append({
                "id": f"esp_{k.lower().replace(' ', '_')}", 
                "title": k, 
                "description": desc
            })
            
        return self.wa.enviar_lista(
            wa_id, 
            "Especialidades", 
            "Selecciona una:", 
            "Mr. Bigo's", 
            "Ver Lista", 
            [{"title": "Nuestras Pizzas", "rows": rows}]
        )
    def _enviar_tamanos(self, wa_id):
        rows = [{"id": k, "title": k.capitalize(), "description": f"${v}"} for k, v in MENU_PIZZAS.items() if k != "promo_pepperoni"]
        return self.wa.enviar_lista(wa_id, "Tamaños", "Elige el tamaño:", "Pizzas", "Seleccionar", [{"title":"Opciones", "rows":rows}])

    def _enviar_ingredientes(self, wa_id, lista, nombre_cat, prefijo):
        rows = [{"id": f"ing_{prefijo}_{i}", "title": ing} for i, ing in enumerate(lista)]
        return self.wa.enviar_lista(wa_id, f"Lista: {nombre_cat}", "Selecciona uno:", "Mr. Bigo's", "Ver Lista", [{"title":nombre_cat, "rows":rows}])

    def _finalizar_orden(self, wa_id, cliente, pedido):
        p = Pedido(cliente_id=cliente.id, total=pedido["total"], detalles_json=json.dumps(pedido), tipo_entrega=pedido["tipo_entrega"])
        db.session.add(p)
        cliente.paso_actual = "INICIO"
        db.session.commit()
        resumen = f"🧾 *ORDEN MR. BIGO'S #{p.id}*\n"
        for i, pizza in enumerate(pedido["pizzas"]):
            resumen += f"🍕 Pizza {i+1}: {pizza['nombre']}\n   ({', '.join(pizza['ingredientes'])})\n"
        if pedido["extras"]: resumen += f"🥤 Extras: {', '.join(pedido['extras'])}\n"
        resumen += f"💰 *TOTAL: ${pedido['total']}*\n¡Gracias!"
        return self.wa.enviar_texto(wa_id, resumen)