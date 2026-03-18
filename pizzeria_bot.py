from models import db, Cliente, Pedido
import json

MENU_PIZZAS = {"familiar": 150, "mediana": 130, "chica": 80}
MENU_EXTRAS = {"spagguetti": 80, "ensalada": 60, "queso": 100, "soda": 50}

INGREDIENTES_PROT = ["Jamón", "Salami", "Peperoni", "Tocino", "Machaca", "Atún", "Salchicha", "Chorizo", "Chilorio"]
INGREDIENTES_VEG = ["Jalapeño", "Aceituna", "Champiñones", "Pimientos", "Tomate", "Piña", "Elote", "Cereza", "Cebolla"]

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

        if texto.lower() == "hola":
            cliente.paso_actual = "MENU_PRINCIPAL"
            cliente.pedido_temporal = json.dumps({"ingredientes": [], "extras": [], "total": 0})
            db.session.commit()
            return self._enviar_menu_principal(wa_id, cliente)

        paso = cliente.paso_actual
        pedido = json.loads(cliente.pedido_temporal)

        # --- FLUJO DE ESTADOS ---
        
        if paso == "MENU_PRINCIPAL":
            if inter_id == "ver_pizzas":
                cliente.paso_actual = "PIZZA_TAMANO"
                db.session.commit()
                return self._enviar_tamanos(wa_id)
            elif inter_id in MENU_EXTRAS:
                pedido["extras"].append(inter_id)
                pedido["total"] += MENU_EXTRAS[inter_id]
                cliente.pedido_temporal = json.dumps(pedido)
                db.session.commit()
                return self.wa.enviar_botones(wa_id, f"✅ *{inter_id.capitalize()}* añadido. ¿Algo más?", 
                                           [{"id":"hola","title":"Ver Menú"},{"id":"pagar","title":"💳 Pagar"}])

        elif paso == "PIZZA_TAMANO":
            if inter_id in MENU_PIZZAS:
                pedido["tamano"] = inter_id
                pedido["total"] += MENU_PIZZAS[inter_id]
                cliente.paso_actual = "PIZZA_INGREDIENTES" # Cambiamos a ingredientes directo
                cliente.pedido_temporal = json.dumps(pedido)
                db.session.commit()
                return self.wa.enviar_botones(wa_id, "¡Excelente! Tu pizza incluye 3 ingredientes.\n¿De qué categoría quieres elegir?", 
                                           [{"id":"cat_prot","title":"🥩 Proteínas"},{"id":"cat_veg","title":"🌿 Vegetales"}])

        elif paso == "PIZZA_INGREDIENTES":
            # 1. Si el usuario presiona una categoría estando en este estado
            if inter_id == "cat_prot":
                return self._enviar_ingredientes(wa_id, INGREDIENTES_PROT, "Proteínas", "prot")
            elif inter_id == "cat_veg":
                return self._enviar_ingredientes(wa_id, INGREDIENTES_VEG, "Vegetales", "veg")
            
            # 2. Si el usuario termina
            elif inter_id == "fin_ing":
                cliente.paso_actual = "MENU_PRINCIPAL"
                db.session.commit()
                return self.wa.enviar_botones(wa_id, "🍕 Pizza lista. ¿Algo más o pasamos al pago?", 
                                           [{"id":"hola","title":"🥤 Ver Extras"},{"id":"pagar","title":"💳 Pagar"}])
            
            # 3. Si el usuario selecciona un ingrediente
            elif inter_id and ("_prot_" in inter_id or "_veg_" in inter_id):
                partes = inter_id.split("_")
                tipo, idx = partes[1], int(partes[2])
                ing = INGREDIENTES_PROT[idx] if tipo == "prot" else INGREDIENTES_VEG[idx]
                
                if ing not in pedido["ingredientes"]:
                    pedido["ingredientes"].append(ing)
                    if len(pedido["ingredientes"]) > 3: pedido["total"] += 20
                
                cliente.pedido_temporal = json.dumps(pedido)
                db.session.commit()
                
                cant = len(pedido["ingredientes"])
                msg = f"✅ *{ing}* añadido ({cant}/3 gratis).\n¿Deseas otro ingrediente o terminar?"
                return self.wa.enviar_botones(wa_id, msg, [{"id":"cat_prot","title":"🥩 Proteínas"},{"id":"cat_veg","title":"🌿 Vegetales"},{"id":"fin_ing","title":"🏁 Terminar"}])

        # --- PAGO Y ENTREGA ---
        if inter_id == "pagar" or texto.lower() == "pagar":
            cliente.paso_actual = "ENTREGA"
            db.session.commit()
            return self.wa.enviar_botones(wa_id, "¿Cómo recibes tu pedido?", [{"id":"dom","title":"🛵 Domicilio"},{"id":"rec","title":"🛍️ Recoger"}])

        elif paso == "ENTREGA":
            pedido["tipo_entrega"] = "domicilio" if inter_id == "dom" else "recoger"
            cliente.pedido_temporal = json.dumps(pedido)
            if inter_id == "rec": return self._finalizar_orden(wa_id, cliente, pedido)
            
            if cliente.ultima_direccion:
                cliente.paso_actual = "CONFIRMAR_DIR"
                db.session.commit()
                return self.wa.enviar_botones(wa_id, f"📍 ¿Usamos tu dirección anterior?\n_{cliente.ultima_direccion}_", 
                                           [{"id":"si_dir","title":"✅ Sí"},{"id":"no_dir","title":"✏️ Otra"}])
            cliente.paso_actual = "DIRECCION"
            db.session.commit()
            return self.wa.enviar_texto(wa_id, "Dime tu dirección completa para el envío:")

        elif paso == "DIRECCION" or paso == "CONFIRMAR_DIR":
            direccion = cliente.ultima_direccion if inter_id == "si_dir" else texto
            pedido["direccion"] = direccion
            cliente.ultima_direccion = direccion
            db.session.commit()
            return self._finalizar_orden(wa_id, cliente, pedido)

    def _enviar_menu_principal(self, wa_id, cliente):
        nombre = cliente.nombre if cliente.nombre else "amigo"
        sections = [
            {"title": "Pizzas", "rows": [{"id":"ver_pizzas", "title":"🍕 Ver Pizzas", "description":"Familiar, Mediana o Chica"}]},
            {"title": "Bebidas y Extras", "rows": [{"id":k, "title":k.capitalize(), "description":f"${v}"} for k,v in MENU_EXTRAS.items()]}
        ]
        return self.wa.enviar_lista(wa_id, "Mesa Code Pizza", f"¡Hola {nombre}! ¿Qué se te antoja?", "Selecciona del menú:", "Ver Menú", sections)

    def _enviar_tamanos(self, wa_id):
        rows = [{"id": k, "title": k.capitalize(), "description": f"${v}"} for k, v in MENU_PIZZAS.items()]
        return self.wa.enviar_lista(wa_id, "Tamaños", "Elige el tamaño:", "Mesa Code", "Seleccionar", [{"title":"Opciones", "rows":rows}])

    def _enviar_ingredientes(self, wa_id, lista, nombre_cat, prefijo):
        rows = [{"id": f"ing_{prefijo}_{i}", "title": ing} for i, ing in enumerate(lista)]
        return self.wa.enviar_lista(wa_id, f"Lista: {nombre_cat}", f"Elige tus {nombre_cat}:", "3 incluidos, extra $20", "Seleccionar", [{"title":nombre_cat, "rows":rows}])

    def _finalizar_orden(self, wa_id, cliente, pedido):
        p = Pedido(cliente_id=cliente.id, total=pedido["total"], detalles_json=json.dumps(pedido), tipo_entrega=pedido["tipo_entrega"])
        db.session.add(p)
        cliente.paso_actual = "INICIO"
        db.session.commit()
        ticket = f"🧾 *ORDEN #{p.id}*\n"
        if "tamano" in pedido: ticket += f"🍕 Pizza {pedido['tamano'].capitalize()}\n"
        ticket += f"🧀 Ing: {', '.join(pedido['ingredientes'])}\n"
        if pedido['extras']: ticket += f"🥤 Ext: {', '.join(pedido['extras'])}\n"
        ticket += f"💰 *TOTAL: ${pedido['total']}*\n⏳ Espera: *40 min*."
        return self.wa.enviar_texto(wa_id, ticket)