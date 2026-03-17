from models import db, Cliente, Pedido
import json

# Datos extraídos de tus capturas
MENU_PRECIOS = {"familiar": 150, "mediana": 130, "chica": 80}
INGREDIENTES_LISTA = [
    "Jamón", "Salami", "Peperoni", "Tocino", "Machaca", "Jalapeño", 
    "Aceituna", "Atún", "Salchicha", "Champiñones", "Pimientos", 
    "Tomate", "Chorizo", "Piña", "Elote", "Cereza", "Chilorio", "Cebolla"
]

# Diccionario de estados en memoria
sesiones = {}

class PizzeriaBot:
    def __init__(self, config, wa_service):
        self.wa = wa_service
        self.config = config

    def gestionar_mensaje(self, wa_id, texto, inter_id=None):
        # Normalizar número México
        if wa_id.startswith("521") and len(wa_id) == 13: wa_id = "52" + wa_id[3:]
        
        if wa_id not in sesiones:
            sesiones[wa_id] = {"paso": "INICIO", "pedido": {"ingredientes": []}}
        
        s = sesiones[wa_id]
        cliente = Cliente.query.filter_by(telefono=wa_id).first()

        # --- FLUJO ---
        if s["paso"] == "INICIO" or texto.lower() == "hola":
            s["paso"] = "TAMAÑO"
            saludo = f"🍕 ¡Hola {cliente.nombre if cliente else ''}! Bienvenido a Mesa Code Pizza.\n¿Qué tamaño deseas?"
            rows = [{"id": k, "title": k.capitalize(), "description": f"${v}"} for k, v in MENU_PRECIOS.items()]
            return self.wa.enviar_lista(wa_id, "Menú", saludo, "Elige uno:", "Ver Tamaños", [{"title": "Pizzas", "rows": rows}])

        if s["paso"] == "TAMAÑO":
            s["pedido"]["tamano"] = inter_id
            s["paso"] = "INGREDIENTES"
            rows = [{"id": f"ing_{i}", "title": ing} for i, ing in enumerate(INGREDIENTES_LISTA)]
            return self.wa.enviar_lista(wa_id, "Ingredientes", "Elige hasta 3 ingredientes incluidos:", "Paso 1/3", "Ver Lista", [{"title": "Opciones", "rows": rows}])

        if s["paso"] == "INGREDIENTES":
            ing_nombre = INGREDIENTES_LISTA[int(inter_id.split("_")[1])]
            if ing_nombre not in s["pedido"]["ingredientes"]: s["pedido"]["ingredientes"].append(ing_nombre)
            
            cant = len(s["pedido"]["ingredientes"])
            if cant < 3:
                return self.wa.enviar_texto(wa_id, f"✅ {ing_nombre} añadido ({cant}/3). Elige otro de la lista arriba.")
            
            s["paso"] = "ENTREGA"
            return self.wa.enviar_botones(wa_id, "¡Listo! ¿Cómo recibes tu pizza?", [{"id":"dom","title":"🛵 Domicilio"},{"id":"rec","title":"🛍️ Recoger"}])

        if s["paso"] == "ENTREGA":
            s["pedido"]["entrega"] = "domicilio" if inter_id == "dom" else "recogida"
            if s["pedido"]["entrega"] == "recogida": return self.finalizar(wa_id, s, cliente)
            
            if cliente and cliente.ultima_direccion:
                s["paso"] = "CONFIRMAR_DIR"
                return self.wa.enviar_botones(wa_id, f"¿Enviamos a tu dirección guardada?\n📍 {cliente.ultima_direccion}", [{"id":"si_dir","title":"✅ Sí"},{"id":"no_dir","title":"❌ Otra"}])
            
            s["paso"] = "NOMBRE"
            return self.wa.enviar_texto(wa_id, "Dime tu nombre para el pedido:")

        if s["paso"] == "NOMBRE":
            s["pedido"]["nombre"] = texto
            s["paso"] = "DIRECCION"
            return self.wa.enviar_texto(wa_id, "Ahora dime tu calle y número:")

        if s["paso"] == "DIRECCION":
            s["pedido"]["direccion"] = texto
            self.actualizar_cliente(wa_id, s["pedido"]["nombre"], texto)
            return self.finalizar(wa_id, s, cliente)

        if s["paso"] == "CONFIRMAR_DIR":
            if inter_id == "si_dir":
                s["pedido"]["direccion"] = cliente.ultima_direccion
                return self.finalizar(wa_id, s, cliente)
            s["paso"] = "DIRECCION"
            return self.wa.enviar_texto(wa_id, "Escribe la nueva dirección:")

    def actualizar_cliente(self, tel, nom, dir):
        c = Cliente.query.filter_by(telefono=tel).first()
        if not c: c = Cliente(telefono=tel)
        if nom: c.nombre = nom
        c.ultima_direccion = dir
        db.session.add(c)
        db.session.commit()

    def finalizar(self, wa_id, s, cliente):
        total = MENU_PRECIOS[s["pedido"]["tamano"]]
        ped = Pedido(cliente_id=cliente.id if cliente else None, total=total, detalles_json=json.dumps(s["pedido"]), tipo_entrega=s["pedido"]["entrega"])
        db.session.add(ped)
        db.session.commit()
        resumen = f"✅ *Pedido Confirmado*\n🍕 {s['pedido']['tamano']}\n🧀 {', '.join(s['pedido']['ingredientes'])}\n💰 Total: ${total}\n⏳ Tiempo: *40 min*."
        sesiones.pop(wa_id)
        return self.wa.enviar_texto(wa_id, resumen)