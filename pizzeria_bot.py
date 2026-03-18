# /Users/alejandromeza/WA_BOT_PROJECTN/pizzeria_bot.py
from models import db, Cliente, Pedido
import json

# --- CONFIGURACIÓN DE MENÚ MR. BIGO'S ---
MENU_PIZZAS = {"familiar": 170, "grande": 150, "mediana": 130}
MENU_PIZZAS_BONELESS = {"familiar": 250, "grande": 210} 
MENU_COMBOS = {"combo_grande": 300, "combo_familiar": 370}
MENU_SNACKS = {"ensalada": 65, "espaguetti": 85, "crazy_papas": 85, "boneless": 120, "alitas": 130}

SALSAS = ["BBQ", "Búfalo", "Kukis", "Tamarindo", "Mango"]
TIPOS_PAPAS = ["Francesa", "Gajo", "Sazonadas"]
SODA_SABORES = ["Coca-Cola", "Sprite", "Fanta", "Manzanita", "Fresa"]

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
            # Normalización del teléfono para México
            if wa_id.startswith("521"): wa_id = "52" + wa_id[3:]
            cliente = Cliente.query.filter_by(telefono=wa_id).first()
            
            # 1. REGISTRO DE CLIENTES NUEVOS
            if not cliente:
                cliente = Cliente(telefono=wa_id, paso_actual="REG_NOMBRE")
                db.session.add(cliente); db.session.commit()
                return self.wa.enviar_texto(wa_id, "¡Hola! Bienvenido a *Mr. Bigo's Pizza*. 🍕\nVeo que es tu primera vez. ¿Cuál es tu **Nombre**?")

            paso = cliente.paso_actual

            # 2. PROCESO DE REGISTRO (BLOQUEANTE)
            if paso.startswith("REG_"):
                if paso == "REG_NOMBRE":
                    cliente.nombre = texto.strip().title()
                    cliente.paso_actual = "REG_APELLIDO"; db.session.commit()
                    return self.wa.enviar_texto(wa_id, f"Mucho gusto {cliente.nombre}. ¿Cuál es tu **Apellido**?")
                elif paso == "REG_APELLIDO":
                    cliente.apellido = texto.strip().title()
                    cliente.paso_actual = "REG_CALLE"; db.session.commit()
                    return self.wa.enviar_texto(wa_id, "Dime el nombre de tu **Calle**:")
                elif paso == "REG_CALLE":
                    cliente.calle = texto.strip()
                    cliente.paso_actual = "REG_NUMERO"; db.session.commit()
                    return self.wa.enviar_texto(wa_id, "¿Cuál es el **Número** de casa?")
                elif paso == "REG_NUMERO":
                    cliente.numero = texto.strip()
                    cliente.paso_actual = "REG_CRUCES"; db.session.commit()
                    return self.wa.enviar_texto(wa_id, "¿Entre qué calles está? (**Cruzamientos**):")
                elif paso == "REG_CRUCES":
                    cliente.cruzamientos = texto.strip()
                    cliente.paso_actual = "REG_REF"; db.session.commit()
                    return self.wa.enviar_texto(wa_id, "Por último, una **Referencia** visual:")
                elif paso == "REG_REF":
                    cliente.referencia = texto.strip()
                    cliente.paso_actual = "MENU_PRINCIPAL"; db.session.commit()
                    return self.wa.enviar_botones(wa_id, "¡Registro completado! ✅\n\n¿Qué pedimos hoy?", [{"id":"hola","title":"Ver Menú"}])

            # 3. NAVEGACIÓN GENERAL (Solo después del registro)
            if (texto.lower() == "hola" and inter_id is None) or inter_id == "hola":
                cliente.paso_actual = "MENU_PRINCIPAL"
                if inter_id is None: cliente.pedido_temporal = json.dumps({"pizzas": [], "extras": [], "total": 0})
                db.session.commit()
                return self._enviar_menu_principal(wa_id, cliente)

            pedido = json.loads(cliente.pedido_temporal)

            # --- MÁQUINA DE ESTADOS DEL PEDIDO ---
            if paso == "MENU_PRINCIPAL":
                if inter_id == "cat_pizzas":
                    cliente.paso_actual = "PIZZA_TAMANO"; db.session.commit()
                    return self._enviar_tamanos(wa_id)
                
                elif inter_id in MENU_COMBOS:
                    pedido["total"] += MENU_COMBOS[inter_id]; pedido["pizzas_por_configurar"] = 2
                    pedido["tamano_actual"] = "grande" if inter_id == "combo_grande" else "familiar"
                    pedido["combo_activo"] = inter_id
                    snack = "Ensalada" if inter_id == "combo_grande" else "Espaguetti"
                    pedido["extras"].append({"nombre": f"{snack} (Combo)", "precio": 0})
                    cliente.paso_actual = "COMBO_SODA"
                    cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                    return self._enviar_sodas(wa_id, f"🎁 *{inter_id.replace('_',' ').title()}*.\nIncluye 2 Pizzas, 1 {snack} y 1 Soda.\nElige el sabor de tu **Soda**:")

                elif inter_id in MENU_SNACKS:
                    pedido["item_en_proceso"] = inter_id
                    cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                    if "boneless" in inter_id or inter_id == "alitas":
                        cliente.paso_actual = "SNACK_SALSA"; db.session.commit(); return self._enviar_salsas(wa_id)
                    elif inter_id == "crazy_papas":
                        cliente.paso_actual = "SNACK_PAPA"; db.session.commit(); return self._enviar_papas(wa_id)
                    else:
                        n, p = inter_id.replace('_',' ').capitalize(), MENU_SNACKS[inter_id]
                        pedido["extras"].append({"nombre": n, "precio": p})
                        pedido["total"] += p; pedido.pop("item_en_proceso", None)
                        cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                        return self.wa.enviar_botones(wa_id, f"✅ {n} añadido.", [{"id":"hola","title":"Menú"},{"id":"pagar","title":"Pagar"}])

            elif paso == "COMBO_SODA":
                if inter_id in SODA_SABORES:
                    pedido["extras"].append({"nombre": f"Soda {inter_id} (Combo)", "precio": 0})
                    cliente.paso_actual = "PIZZA_MODO"
                    cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                    return self.wa.enviar_botones(wa_id, f"✅ Soda {inter_id} elegida.\nConfiguremos la *Pizza 1*:", [{"id":"modo_full","title":"🍕 Completa"},{"id":"modo_mitad","title":"🌗 Mitad y Mitad"}])

            elif paso == "SNACK_SALSA":
                if inter_id in SALSAS:
                    item = pedido.pop("item_en_proceso", "Snack")
                    n, p = f"{item.capitalize()} ({inter_id})", MENU_SNACKS.get(item, 0)
                    pedido["extras"].append({"nombre": n, "precio": p})
                    pedido["total"] += p
                    cliente.paso_actual = "MENU_PRINCIPAL"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                    return self.wa.enviar_botones(wa_id, f"✅ Añadido. Total: ${pedido['total']}", [{"id":"hola","title":"Menú"},{"id":"pagar","title":"Pagar"}])

            elif paso == "SNACK_PAPA":
                if inter_id in TIPOS_PAPAS:
                    pedido.pop("item_en_proceso", "crazy_papas")
                    n, p = f"Crazy Papas {inter_id}", 85
                    pedido["extras"].append({"nombre": n, "precio": p})
                    pedido["total"] += p
                    cliente.paso_actual = "MENU_PRINCIPAL"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                    return self.wa.enviar_botones(wa_id, f"✅ Papas {inter_id} añadidas.", [{"id":"hola","title":"Menú"},{"id":"pagar","title":"Pagar"}])

            elif paso == "PIZZA_TAMANO":
                if inter_id in MENU_PIZZAS:
                    pedido["tamano_actual"] = inter_id; pedido["pizzas_por_configurar"] = 1
                    cliente.paso_actual = "PIZZA_MODO"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                    return self.wa.enviar_botones(wa_id, f"Pizza {inter_id.capitalize()}.\n¿Cómo la quieres?", [{"id":"modo_full","title":"🍕 Completa"},{"id":"modo_mitad","title":"🌗 Mitad y Mitad"}])

            elif paso == "PIZZA_MODO":
                pedido["modo_actual"] = inter_id
                cliente.paso_actual = "PIZZA_TIPO_ELECCION"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                prmt = "Elige el sabor:" if inter_id == "modo_full" else "Sabor de la *Primera Mitad*:"
                return self.wa.enviar_botones(wa_id, prmt, [{"id":"tipo_esp","title":"🌟 Especialidad"},{"id":"tipo_ing","title":"👨‍🍳 Armarla"}])

            elif paso == "PIZZA_TIPO_ELECCION":
                if inter_id == "tipo_esp": return self._enviar_especialidades(wa_id)
                elif inter_id == "tipo_ing":
                    cliente.paso_actual = "PIZZA_INGREDIENTES"; db.session.commit()
                    return self.wa.enviar_botones(wa_id, "Elige ingredientes (5 gratis):", [{"id":"cat_prot","title":"🥩 Proteínas"},{"id":"cat_veg","title":"🌿 Vegetales"}])

            elif paso == "PIZZA_INGREDIENTES":
                if inter_id == "cat_prot": return self._enviar_ingredientes(wa_id, INGREDIENTES_PROT, "Prot", "prot")
                elif inter_id == "cat_veg": return self._enviar_ingredientes(wa_id, INGREDIENTES_VEG, "Veg", "veg")
                elif inter_id and ("_prot_" in inter_id or "_veg_" in inter_id):
                    partes = inter_id.split("_"); tipo, idx = partes[1], int(partes[2])
                    ing = INGREDIENTES_PROT[idx] if tipo == "prot" else INGREDIENTES_VEG[idx]
                    if "armando" not in pedido: pedido["armando"] = []
                    if ing not in pedido["armando"]:
                        pedido["armando"].append(ing)
                        if len(pedido["armando"]) > 5: pedido["total"] += 20
                    cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                    cant = len(pedido["armando"])
                    aviso = "\n\n⚠️ El próximo cuesta $20." if cant == 5 else ""
                    return self.wa.enviar_botones(wa_id, f"✅ {ing} ({cant}/5).{aviso}\n📝 Llevas: {', '.join(pedido['armando'])}", [{"id":"cat_prot","title":"🥩 Prot"},{"id":"cat_veg","title":"🌿 Veg"},{"id":"fin_pizza","title":"🏁 Terminar"}])
                elif inter_id == "fin_pizza":
                    return self._procesar_seleccion_sabor(wa_id, cliente, pedido, "Armada", pedido.pop("armando", []))

            elif paso == "PIZZA_ESPECIALIDAD":
                if inter_id.startswith("esp_"):
                    # Corrección de Carnes Frías y nombres con guión
                    nombre_esp = inter_id[4:].replace("_", " ").title()
                    if nombre_esp == "Boneless":
                        cliente.paso_actual = "PIZZA_SALSA_BONELESS"; db.session.commit(); return self._enviar_salsas(wa_id)
                    return self._procesar_seleccion_sabor(wa_id, cliente, pedido, nombre_esp, ESPECIALIDADES.get(nombre_esp, []))

            elif paso == "PIZZA_SALSA_BONELESS":
                if inter_id in SALSAS:
                    return self._procesar_seleccion_sabor(wa_id, cliente, pedido, f"Boneless ({inter_id})", ["Boneless", inter_id])

            # --- NUEVO: FIX BUCLE DE EDICIÓN ---
            if inter_id == "modificar_pedido":
                cliente.paso_actual = "MODIFICAR_CARRITO"; db.session.commit()
                return self._enviar_lista_edicion(wa_id, pedido)
            
            elif paso == "MODIFICAR_CARRITO":
                if inter_id.startswith("del_pz_"):
                    idx = int(inter_id.split("_")[-1])
                    pz = pedido["pizzas"].pop(idx); pedido["total"] -= pz.get("precio", 0)
                elif inter_id.startswith("del_ex_"):
                    idx = int(inter_id.split("_")[-1])
                    ex = pedido["extras"].pop(idx); pedido["total"] -= ex.get("precio", 0)
                
                # CRÍTICO: Regresamos el estado a CONFIRMACION tras editar
                cliente.paso_actual = "CONFIRMACION"
                cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                return self._enviar_resumen(wa_id, pedido)

            # --- BLOQUE DE CONFIRMACIÓN ---
            if inter_id == "pagar":
                cliente.paso_actual = "CONFIRMACION"; db.session.commit()
                return self._enviar_resumen(wa_id, pedido)
            
            elif paso == "CONFIRMACION":
                if inter_id == "ok_pedido":
                    cliente.paso_actual = "ENTREGA"; db.session.commit()
                    return self.wa.enviar_botones(wa_id, "¿Cómo recibes tu orden?", [{"id":"dom","title":"🛵 Domicilio"},{"id":"rec","title":"🛍️ Recoger"}])
                elif inter_id == "cancel_pedido":
                    return self.gestionar_pedido(wa_id, "hola", "hola")

            elif paso == "ENTREGA":
                pedido["tipo_entrega"] = "domicilio" if inter_id == "dom" else "recoger"
                cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                if inter_id == "rec": return self._finalizar_orden(wa_id, cliente, pedido)
                df = f"{cliente.calle} #{cliente.numero}, {cliente.cruzamientos} ({cliente.referencia})"
                cliente.paso_actual = "CONFIRMAR_DIR"; db.session.commit()
                return self.wa.enviar_botones(wa_id, f"📍 ¿Enviar a esta dirección?\n_{df}_", [{"id":"dir_si","title":"✅ Sí"},{"id":"dir_no","title":"✏️ Otra"}])

            elif paso == "CONFIRMAR_DIR":
                if inter_id == "dir_si":
                    pedido["direccion"] = f"{cliente.calle} #{cliente.numero}, {cliente.cruzamientos} ({cliente.referencia})"
                    return self._finalizar_orden(wa_id, cliente, pedido)
                cliente.paso_actual = "DIR_NUEVA"; db.session.commit()
                return self.wa.enviar_texto(wa_id, "Dime la **nueva dirección** completa:")
            elif paso == "DIR_NUEVA":
                pedido["direccion"] = texto; return self._finalizar_orden(wa_id, cliente, pedido)

        except Exception as e: print(f"❌ ERROR BOT: {e}", flush=True)

    # --- LÓGICA DE PRECIOS ---
    def _procesar_seleccion_sabor(self, wa_id, cliente, pedido, nombre_sabor, ingredientes):
        modo, tam = pedido.get("modo_actual"), pedido.get("tamano_actual", "grande")
        p_pz = 0
        if modo == "modo_full":
            if "combo_activo" not in pedido:
                p_pz = MENU_PIZZAS_BONELESS[tam] if "Boneless" in nombre_sabor else MENU_PIZZAS[tam]
                pedido["total"] += p_pz
            elif "Boneless" in nombre_sabor: p_pz = 20; pedido["total"] += 20
            pedido["pizzas"].append({"nombre": f"Completa {nombre_sabor}", "ingredientes": ingredientes, "tamano": tam, "precio": p_pz})
            return self._verificar_siguiente_paso(wa_id, cliente, pedido)
        elif modo == "modo_mitad":
            if "mitad_a" not in pedido:
                pedido["mitad_a"] = {"nombre": nombre_sabor, "ingredientes": ingredientes}
                cliente.paso_actual = "PIZZA_TIPO_ELECCION"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                return self.wa.enviar_botones(wa_id, "¡Sabor 1 listo! Elige el sabor de la *Segunda Mitad*:", [{"id":"tipo_esp","title":"🌟 Especialidad"},{"id":"tipo_ing","title":"👨‍🍳 Armarla"}])
            else:
                m_a, m_b = pedido.pop("mitad_a"), {"nombre": nombre_sabor, "ingredientes": ingredientes}
                has_bl = "Boneless" in m_a["nombre"] or "Boneless" in m_b["nombre"]
                if "combo_activo" not in pedido:
                    if "Boneless" in m_a["nombre"] and "Boneless" in m_b["nombre"]: p_pz = MENU_PIZZAS_BONELESS[tam]
                    elif has_bl: p_pz = MENU_PIZZAS[tam] + 20
                    else: p_pz = MENU_PIZZAS[tam]
                    pedido["total"] += p_pz
                elif has_bl: p_pz = 20; pedido["total"] += 20
                pedido["pizzas"].append({"nombre": f"Mitad {m_a['nombre']} / {m_b['nombre']}", "ingredientes": m_a["ingredientes"]+m_b["ingredientes"], "tamano": tam, "precio": p_pz})
                return self._verificar_siguiente_paso(wa_id, cliente, pedido)

    def _verificar_siguiente_paso(self, wa_id, cliente, pedido):
        pedido["pizzas_por_configurar"] -= 1; pedido.pop("modo_actual", None)
        if pedido["pizzas_por_configurar"] > 0:
            cliente.paso_actual = "PIZZA_MODO"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
            return self.wa.enviar_botones(wa_id, f"Pizza 1 lista. Configura la *Pizza 2*:", [{"id":"modo_full","title":"🍕 Completa"},{"id":"modo_mitad","title":"🌗 Mitad y Mitad"}])
        cliente.paso_actual = "MENU_PRINCIPAL"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
        return self.wa.enviar_botones(wa_id, f"✅ Agregado. Total: *${pedido['total']}*", [{"id":"hola","title":"Menú"},{"id":"pagar","title":"Pagar"}])

    # --- ENVÍOS ---
    def _enviar_menu_principal(self, wa_id, cliente):
        total = json.loads(cliente.pedido_temporal).get("total", 0)
        sections = [{"title": "Paquetes", "rows": [{"id":"combo_grande","title":"🎁 Combo Grande $300", "description": "2 Gdes + Ensalada + Soda 2L"},{"id":"combo_familiar","title":"🎁 Combo Familiar $370", "description": "2 Fam + Espaguetti + Soda 2L"}]},{"title": "Individuales", "rows": [{"id":"cat_pizzas","title":"🍕 Armar Pizza"}]},{"title": "Snacks", "rows": [{"id":k, "title":k.replace('_',' ').capitalize(), "description":f"${v}"} for k,v in MENU_SNACKS.items()]}]
        return self.wa.enviar_lista(wa_id, "Mr. Bigo's Pizza", f"¡Hola {cliente.nombre}! 👋", f"Total: ${total}", "Ver Menú", sections)

    def _enviar_resumen(self, wa_id, pedido):
        res = "📋 *REVISIÓN DE TU PEDIDO*\n\n"
        for i, p in enumerate(pedido["pizzas"]): res += f"🍕 *P{i+1}:* {p['nombre']}\n"
        for ex in pedido["extras"]: res += f"🔸 *{ex['nombre']}*\n"
        res += f"\n💵 *TOTAL FINAL: ${pedido['total']}*"
        return self.wa.enviar_botones(wa_id, res, [{"id":"ok_pedido","title":"✅ Confirmar"},{"id":"modificar_pedido","title":"✏️ Editar"},{"id":"cancel_pedido","title":"❌ Reiniciar"}])

    def _enviar_sodas(self, wa_id, body_text):
        rows = [{"id": s, "title": s} for s in SODA_SABORES]
        return self.wa.enviar_lista(wa_id, "Bebidas", body_text, "Bigo's", "Ver Sabores", [{"title":"Sodas 2L", "rows":rows}])

    def _enviar_lista_edicion(self, wa_id, pedido):
        rows = []
        for i, pz in enumerate(pedido["pizzas"]): rows.append({"id": f"del_pz_{i}", "title": f"Quitar Pizza {i+1}", "description": f"{pz['nombre'][:70]}"})
        for i, ex in enumerate(pedido["extras"]): rows.append({"id": f"del_ex_{i}", "title": f"Quitar Item {i+1}", "description": f"{ex['nombre'][:70]}"})
        return self.wa.enviar_lista(wa_id, "Editar Carrito", "Toca para eliminar un elemento:", "Bigo's", "Ver Carrito", [{"title":"Tu Orden", "rows":rows}])

    def _enviar_especialidades(self, wa_id):
        cliente = Cliente.query.filter_by(telefono=wa_id).first(); cliente.paso_actual = "PIZZA_ESPECIALIDAD"; db.session.commit()
        rows = [{"id": f"esp_{k.lower().replace(' ', '_')}", "title": k, "description": ", ".join(v)[:70]} for k, v in ESPECIALIDADES.items()]
        return self.wa.enviar_lista(wa_id, "Sabor", "Elige:", "Bigo's", "Sabores", [{"title":"Lista", "rows":rows}])

    def _enviar_tamanos(self, wa_id):
        rows = [{"id": k, "title": k.capitalize(), "description": f"Desde ${v}"} for k, v in MENU_PIZZAS.items()]
        return self.wa.enviar_lista(wa_id, "Tamaños", "Elige:", "Bigo's", "Seleccionar", [{"title":"Opciones", "rows":rows}])

    def _enviar_salsas(self, wa_id):
        rows = [{"id": s, "title": s} for s in SALSAS]; return self.wa.enviar_lista(wa_id, "Salsas", "Elige:", "Bigo's", "Salsas", [{"title":"Salsas", "rows":rows}])

    def _enviar_papas(self, wa_id):
        rows = [{"id": p, "title": p} for p in TIPOS_PAPAS]; return self.wa.enviar_lista(wa_id, "Papas", "Estilo:", "Bigo's", "Papas", [{"title":"Tipos", "rows":rows}])

    def _enviar_ingredientes(self, wa_id, lista, nombre_cat, prefijo):
        rows = [{"id": f"ing_{prefijo}_{i}", "title": ing} for i, ing in enumerate(lista)]
        return self.wa.enviar_lista(wa_id, f"Lista: {nombre_cat}", "Selecciona:", "Bigo's", "Ver Lista", [{"title":nombre_cat, "rows":rows}])

    def _finalizar_orden(self, wa_id, cliente, pedido):
        p = Pedido(cliente_id=cliente.id, total=pedido["total"], detalles_json=json.dumps(pedido), tipo_entrega=pedido["tipo_entrega"])
        db.session.add(p); cliente.paso_actual = "INICIO"; db.session.commit()
        return self.wa.enviar_texto(wa_id, f"🧾 *ORDEN REALIZADA #{p.id}*\n💰 Total: *${pedido['total']}*\n¡Gracias por elegir Mr. Bigo's!")