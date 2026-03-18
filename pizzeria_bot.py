# /Users/alejandromeza/WA_BOT_PROJECTN/pizzeria_bot.py
from models import db, Cliente, Pedido
import json

# --- DATA MR. BIGO'S ---
MENU_PIZZAS = {"familiar": 170, "grande": 150, "mediana": 130}
MENU_PIZZAS_BONELESS = {"familiar": 250, "grande": 210} 
MENU_COMBOS = {"combo_grande": 300, "combo_familiar": 370}
MENU_SNACKS = {"ensalada": 65, "espaguetti": 85, "crazy_papas": 85, "boneless": 120, "alitas": 130}

SALSAS = ["BBQ", "Búfalo", "Kukis", "Tamarindo", "Mango"]
TIPOS_PAPAS = ["Francesa", "Gajo", "Sazonadas"]

ESPECIALIDADES = {
    "Suprema": ["Salami", "Champiñón", "Pimiento verde", "Aceituna negra", "Cebolla blanca", "Pepperoni", "Elote"],
    "Mexicana": ["Tocino", "Chorizo", "Jalapeño", "Frijol"],
    "Carnes Frías": ["Jamón", "Salchicha", "Tocino", "Salami"],
    "Italiana": ["Salchicha", "Pepperoni", "Aceituna negra", "Champiñón", "Pimiento verde"],
    "Hawaiana": ["Jamón", "Cereza", "Piña"],
    "Culichi": ["Chilorio", "Champiñón", "Pimiento verde"],
    "Sonora": ["Machaca", "Cebolla cambray", "Chile verde"],
    "Bigo Express": ["Pepperoni"],
    "Boneless": ["Boneless", "Salsa a elegir"]
}

INGREDIENTES_PROT = ["Jamón", "Salami", "Pepperoni", "Tocino", "Chorizo", "Salchicha", "Chilorio", "Machaca"]
INGREDIENTES_VEG = ["Champiñón", "Pimiento Verde", "Aceituna Negra", "Cebolla Blanca", "Elote", "Jalapeño", "Frijol", "Piña", "Cereza", "Chile Verde"]

class PizzeriaBot:
    def __init__(self, config, wa_service):
        self.wa = wa_service
        self.config = config

    def gestionar_pedido(self, wa_id, texto, inter_id=None):
        try:
            if wa_id.startswith("521"): wa_id = "52" + wa_id[3:]
            cliente = Cliente.query.filter_by(telefono=wa_id).first()
            
            if not cliente:
                cliente = Cliente(telefono=wa_id, paso_actual="REG_NOMBRE")
                db.session.add(cliente); db.session.commit()
                return self.wa.enviar_texto(wa_id, "¡Hola! Bienvenido a *Mr. Bigo's Pizza*. 🍕\nVeo que es tu primera vez aquí. Para darte un mejor servicio, ocupo registrarte.\n\n¿Cuál es tu **Nombre**?")

            # --- FLUJO DE REGISTRO ---
            paso = cliente.paso_actual
            
            if paso == "REG_NOMBRE":
                cliente.nombre = texto.strip().title()
                cliente.paso_actual = "REG_APELLIDO"; db.session.commit()
                return self.wa.enviar_texto(wa_id, f"Mucho gusto {cliente.nombre}. ¿Cuál es tu **Apellido**?")
            
            elif paso == "REG_APELLIDO":
                cliente.apellido = texto.strip().title()
                cliente.paso_actual = "REG_CALLE"; db.session.commit()
                return self.wa.enviar_texto(wa_id, "Gracias. Ahora dime el nombre de tu **Calle**:")
            
            elif paso == "REG_CALLE":
                cliente.calle = texto.strip()
                cliente.paso_actual = "REG_NUMERO"; db.session.commit()
                return self.wa.enviar_texto(wa_id, "¿Cuál es el **Número** de casa o local?")
            
            elif paso == "REG_NUMERO":
                cliente.numero = texto.strip()
                cliente.paso_actual = "REG_CRUCES"; db.session.commit()
                return self.wa.enviar_texto(wa_id, "¿Entre qué calles se encuentra? (**Cruzamientos**):")
            
            elif paso == "REG_CRUCES":
                cliente.cruzamientos = texto.strip()
                cliente.paso_actual = "REG_REF"; db.session.commit()
                return self.wa.enviar_texto(wa_id, "Por último, una **Referencia** (color de casa, portón, etc.):")
            
            elif paso == "REG_REF":
                cliente.referencia = texto.strip()
                cliente.paso_actual = "MENU_PRINCIPAL"; db.session.commit()
                return self.wa.enviar_botones(wa_id, "¡Registro completado! ✅ Ya no tendrás que escribir estos datos de nuevo.\n\n¿Qué se te antoja hoy?", [{"id":"hola","title":"Ver Menú"}])

            # --- FLUJO DE PEDIDO (Solo si ya está registrado) ---
            if (texto.lower() == "hola" and inter_id is None) or inter_id == "hola":
                cliente.paso_actual = "MENU_PRINCIPAL"
                if inter_id is None: # Solo reset si escribe hola manual
                    cliente.pedido_temporal = json.dumps({"pizzas": [], "extras": [], "total": 0})
                db.session.commit()
                return self._enviar_menu_principal(wa_id, cliente)

            pedido = json.loads(cliente.pedido_temporal)

            # ... (Toda la lógica de MENU_PRINCIPAL, PIZZAS, COMBOS se mantiene igual) ...
            # ... (ASEGURARSE DE COPIAR LA LÓGICA DE MITADES Y BONELESS AQUÍ) ...

            # --- ACTUALIZACIÓN EN EL PASO DE ENTREGA ---
            if paso == "ENTREGA":
                pedido["tipo_entrega"] = "domicilio" if inter_id == "dom" else "recoger"
                cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                
                if inter_id == "rec": return self._finalizar_orden(wa_id, cliente, pedido)
                
                # Si es domicilio, usamos la dirección guardada
                direccion_completa = f"{cliente.calle} #{cliente.numero}, entre {cliente.cruzamientos} ({cliente.referencia})"
                cliente.paso_actual = "CONFIRMAR_DIRECCION"
                db.session.commit()
                return self.wa.enviar_botones(wa_id, f"📍 ¿Enviamos a tu dirección registrada?\n\n_{direccion_completa}_", 
                                           [{"id":"dir_si","title":"✅ Sí, ahí"},{"id":"dir_no","title":"✏️ Usar otra"}])

            elif paso == "CONFIRMAR_DIRECCION":
                if inter_id == "dir_si":
                    pedido["direccion"] = f"{cliente.calle} #{cliente.numero}, entre {cliente.cruzamientos} ({cliente.referencia})"
                    return self._finalizar_orden(wa_id, cliente, pedido)
                else:
                    cliente.paso_actual = "DIRECCION_NUEVA"; db.session.commit()
                    return self.wa.enviar_texto(wa_id, "Entendido. Dime la **nueva dirección** completa para este pedido:")

            elif paso == "DIRECCION_NUEVA":
                pedido["direccion"] = texto
                return self._finalizar_orden(wa_id, cliente, pedido)

        except Exception as e:
            print(f"❌ ERROR BOT: {e}", flush=True)

    def _enviar_menu_principal(self, wa_id, cliente):
        total = json.loads(cliente.pedido_temporal).get("total", 0)
        sections = [
            {"title": "Pizzas", "rows": [{"id":"cat_pizzas","title":"🍕 Arma tu Pizza"},{"id":"combo_grande","title":"🎁 Combo Grande $300"},{"id":"combo_familiar","title":"🎁 Combo Familiar $370"}]},
            {"title": "Snacks", "rows": [{"id":k, "title":k.replace('_',' ').capitalize(), "description":f"${v}"} for k,v in MENU_SNACKS.items()]}
        ]
        # SALUDO PERSONALIZADO
        saludo = f"¡Hola {cliente.nombre}! 👋"
        return self.wa.enviar_lista(wa_id, "Mr. Bigo's Pizza", f"{saludo}\nAñade items o finaliza tu orden.", f"Total: ${total}", "Ver Menú", sections)

    # ... (Copiar aquí _procesar_seleccion_sabor, _verificar_siguiente_paso, _enviar_resumen, etc. de tu código anterior) ...

    def _finalizar_orden(self, wa_id, cliente, pedido):
        p = Pedido(cliente_id=cliente.id, total=pedido["total"], detalles_json=json.dumps(pedido), tipo_entrega=pedido["tipo_entrega"])
        db.session.add(p); cliente.paso_actual = "MENU_PRINCIPAL"; db.session.commit()
        
        ticket = f"🧾 *ORDEN REALIZADA #{p.id}*\n"
        ticket += f"👤 Cliente: {cliente.nombre} {cliente.apellido}\n"
        ticket += f"💰 Total: *${pedido['total']}*\n"
        ticket += f"📍 Entrega: {pedido['tipo_entrega'].capitalize()}\n"
        if pedido['tipo_entrega'] == "domicilio":
            ticket += f"🏠 Dirección: {pedido.get('direccion')}\n"
        ticket += "\n¡Gracias por elegir Mr. Bigo's!"
        return self.wa.enviar_texto(wa_id, ticket)