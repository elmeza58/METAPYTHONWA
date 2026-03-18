# /Users/alejandromeza/WA_BOT_PROJECTN/pizzeria_bot.py
from models import db, Cliente, Pedido
import json
import uuid

# --- DATA MR. BIGO'S ---
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
            if wa_id.startswith("521"): wa_id = "52" + wa_id[3:]
            cliente = Cliente.query.filter_by(telefono=wa_id).first()
            
            # --- 1. REGISTRO ---
            if not cliente:
                cliente = Cliente(telefono=wa_id, paso_actual="REG_NOMBRE")
                db.session.add(cliente); db.session.commit()
                return self.wa.enviar_texto(wa_id, "¡Hola! Bienvenido a *Mr. Bigo's Pizza*. 🍕\n¿Cuál es tu **Nombre**?")

            paso = cliente.paso_actual
            # Evitar errores si pedido_temporal está vacío
            try:
                pedido = json.loads(cliente.pedido_temporal)
            except:
                pedido = {"pizzas": [], "extras": [], "total": 0}

            # --- 2. LOGICA DE REGISTRO ---
            if paso.startswith("REG_"):
                if paso == "REG_NOMBRE":
                    cliente.nombre = texto.strip().title(); cliente.paso_actual = "REG_APELLIDO"
                elif paso == "REG_APELLIDO":
                    cliente.apellido = texto.strip().title(); cliente.paso_actual = "REG_CALLE"
                elif paso == "REG_CALLE":
                    cliente.calle = texto.strip(); cliente.paso_actual = "REG_NUMERO"
                elif paso == "REG_NUMERO":
                    cliente.numero = texto.strip(); cliente.paso_actual = "REG_CRUCES"
                elif paso == "REG_CRUCES":
                    cliente.cruzamientos = texto.strip(); cliente.paso_actual = "REG_REF"
                elif paso == "REG_REF":
                    cliente.referencia = texto.strip(); cliente.paso_actual = "MENU_PRINCIPAL"
                    db.session.commit()
                    return self.wa.enviar_botones(wa_id, "¡Registro listo! ✅", [{"id":"hola","title":"Ver Menú"}])
                
                db.session.commit()
                preguntas = {"REG_APELLIDO": "¿Apellido?", "REG_CALLE": "Dime tu **Calle**:", "REG_NUMERO": "¿Número de casa?", "REG_CRUCES": "¿Entre qué calles?", "REG_REF": "Una **Referencia**:"}
                return self.wa.enviar_texto(wa_id, preguntas.get(cliente.paso_actual, "Continuemos..."))

            # --- 3. NAVEGACIÓN ---
            if (texto.lower() == "hola" and inter_id is None) or inter_id == "hola":
                cliente.paso_actual = "MENU_PRINCIPAL"
                if inter_id is None: pedido = {"pizzas": [], "extras": [], "total": 0}
                cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                return self._enviar_menu_principal(wa_id, cliente)

            # --- 4. ESTADOS DEL PEDIDO ---
            if paso == "MENU_PRINCIPAL":
                if inter_id == "cat_pizzas":
                    cliente.paso_actual = "PIZZA_TAMANO"; db.session.commit()
                    return self._enviar_tamanos(wa_id)
                elif inter_id in MENU_COMBOS:
                    c_id = str(uuid.uuid4())[:8]
                    pedido["total"] += MENU_COMBOS[inter_id]; pedido["pizzas_por_configurar"] = 2
                    pedido["tamano_actual"] = "grande" if inter_id == "combo_grande" else "familiar"
                    pedido["combo_id_actual"] = c_id; pedido["combo_activo"] = inter_id
                    sn = "Ensalada" if inter_id == "combo_grande" else "Espaguetti"
                    pedido["extras"].append({"nombre": f"{sn} (Combo)", "precio": 0, "combo_id": c_id, "tipo": "snack_combo"})
                    pedido["extras"].append({"nombre": f"Paquete {pedido['tamano_actual'].capitalize()}", "precio": MENU_COMBOS[inter_id], "combo_id": c_id, "combo_key": inter_id, "tipo": "base_combo"})
                    cliente.paso_actual = "COMBO_SODA"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                    return self._enviar_sodas(wa_id, f"🎁 *Combo {pedido['tamano_actual'].capitalize()}*.\nElige sabor de **Soda**:")
                elif inter_id in MENU_SNACKS:
                    pedido["item_en_proceso"] = inter_id
                    if "boneless" in inter_id or inter_id == "alitas":
                        cliente.paso_actual = "SNACK_SALSA"
                    elif inter_id == "crazy_papas":
                        cliente.paso_actual = "SNACK_PAPA"
                    else:
                        n, p = inter_id.replace('_',' ').capitalize(), MENU_SNACKS[inter_id]
                        pedido["extras"].append({"nombre": n, "precio": p, "combo_id": None})
                        pedido["total"] += p; pedido.pop("item_en_proceso", None)
                        cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                        return self._enviar_confirmacion_item(wa_id, n, pedido['total'])
                    cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                    return self._enviar_salsas(wa_id) if "SNACK_SALSA" in cliente.paso_actual else self._enviar_papas(wa_id)

            elif paso == "SNACK_SALSA":
                if inter_id in SALSAS:
                    item = pedido.pop("item_en_proceso", "Snack")
                    n, p = f"{item.capitalize()} ({inter_id})", MENU_SNACKS.get(item, 0)
                    pedido["extras"].append({"nombre": n, "precio": p, "combo_id": None}); pedido["total"] += p
                    cliente.paso_actual = "MENU_PRINCIPAL"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                    return self._enviar_confirmacion_item(wa_id, n, pedido['total'])

            elif paso == "SNACK_PAPA":
                if inter_id in TIPOS_PAPAS:
                    pedido.pop("item_en_proceso", "crazy_papas")
                    n, p = f"Crazy Papas {inter_id}", 85
                    pedido["extras"].append({"nombre": n, "precio": p, "combo_id": None}); pedido["total"] += p
                    cliente.paso_actual = "MENU_PRINCIPAL"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                    return self._enviar_confirmacion_item(wa_id, n, pedido['total'])

            elif paso == "COMBO_SODA":
                if inter_id in SODA_SABORES:
                    pedido["extras"].append({"nombre": f"Soda {inter_id} (Combo)", "precio": 0, "combo_id": pedido.get("combo_id_actual"), "tipo": "soda_combo"})
                    if pedido.pop("editando_item", False):
                        cliente.paso_actual = "CONFIRMACION"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                        return self._enviar_resumen(wa_id, pedido)
                    cliente.paso_actual = "PIZZA_MODO"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                    return self.wa.enviar_botones(wa_id, f"✅ Soda elegida. Configura la *Pizza 1*:", [{"id":"modo_full","title":"🍕 Completa"},{"id":"modo_mitad","title":"🌗 Mitad y Mitad"}])

            elif paso == "PIZZA_TAMANO":
                if inter_id in MENU_PIZZAS:
                    pedido["tamano_actual"] = inter_id; pedido["pizzas_por_configurar"] = 1
                    cliente.paso_actual = "PIZZA_MODO"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                    return self.wa.enviar_botones(wa_id, f"Pizza {inter_id.capitalize()}.\n¿Cómo la quieres?", [{"id":"modo_full","title":"🍕 Completa"},{"id":"modo_mitad","title":"🌗 Mitad y Mitad"}])

            elif paso == "PIZZA_MODO":
                pedido["modo_actual"] = inter_id; cliente.paso_actual = "PIZZA_TIPO_ELECCION"
                cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                prmt = "Elige el sabor:" if inter_id == "modo_full" else "Sabor de la *Mitad*:"
                return self.wa.enviar_botones(wa_id, prmt, [{"id":"tipo_esp","title":"🌟 Especialidad"},{"id":"tipo_ing","title":"👨‍🍳 Armarla"}])

            elif paso == "PIZZA_TIPO_ELECCION":
                if inter_id == "tipo_esp": return self._enviar_especialidades(wa_id)
                elif inter_id == "tipo_ing":
                    cliente.paso_actual = "PIZZA_INGREDIENTES"; db.session.commit()
                    return self.wa.enviar_botones(wa_id, "Categoría:", [{"id":"cat_prot","title":"🥩 Prot"},{"id":"cat_veg","title":"🌿 Veg"}])

            elif paso == "PIZZA_ESPECIALIDAD":
                if inter_id.startswith("esp_"):
                    nombre_esp = inter_id[4:].replace("_", " ").title()
                    # Parche para Carnes Frías con acento
                    if "Frías" in nombre_esp or "Frias" in nombre_esp: nombre_esp = "Carnes Frías"
                    if nombre_esp == "Boneless":
                        cliente.paso_actual = "PIZZA_SALSA_BONELESS"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                        return self._enviar_salsas(wa_id)
                    return self._procesar_seleccion_sabor(wa_id, cliente, pedido, nombre_esp, ESPECIALIDADES.get(nombre_esp, []))

            elif paso == "PIZZA_SALSA_BONELESS":
                if inter_id in SALSAS: return self._procesar_seleccion_sabor(wa_id, cliente, pedido, f"Boneless ({inter_id})", ["Boneless", inter_id])

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
                    av = "\n\n⚠️ El 6to cuesta $20." if cant == 5 else ""
                    return self.wa.enviar_botones(wa_id, f"✅ {ing} ({cant}/5).{av}\n📝 Llevas: {', '.join(pedido['armando'])}", [{"id":"cat_prot","title":"🥩 Prot"},{"id":"cat_veg","title":"🌿 Veg"},{"id":"fin_pizza","title":"🏁 Terminar"}])
                elif inter_id == "fin_pizza": return self._procesar_seleccion_sabor(wa_id, cliente, pedido, "Armada", pedido.pop("armando", []))

            # --- GESTIÓN DE EDICIÓN ---
            if inter_id == "modificar_pedido":
                cliente.paso_actual = "MODIFICAR_CARRITO"; db.session.commit(); return self._enviar_lista_edicion(wa_id, pedido)
            elif paso == "MODIFICAR_CARRITO":
                if inter_id.startswith("combo_edit_"):
                    pedido["combo_a_gestionar"] = inter_id.replace("combo_edit_", "")
                    cliente.paso_actual = "DECISION_COMBO"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                    return self._enviar_lista_componentes_combo(wa_id, pedido, pedido["combo_a_gestionar"])
                elif inter_id.startswith("del_pz_"):
                    pz = pedido["pizzas"].pop(int(inter_id.split("_")[-1])); pedido["total"] -= pz.get("precio", 0)
                elif inter_id.startswith("del_ex_"):
                    ex = pedido["extras"].pop(int(inter_id.split("_")[-1])); pedido["total"] -= ex.get("precio", 0)
                cliente.paso_actual = "CONFIRMACION"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                return self._enviar_resumen(wa_id, pedido)

            elif paso == "DECISION_COMBO":
                c_id = pedido.get("combo_a_gestionar")
                if inter_id == "del_combo_total":
                    pr = next((ex["precio"] for ex in pedido["extras"] if ex.get("combo_id") == c_id and ex.get("tipo") == "base_combo"), 0)
                    pedido["pizzas"] = [p for p in pedido["pizzas"] if p.get("combo_id") != c_id]
                    pedido["extras"] = [e for e in pedido["extras"] if isinstance(e, dict) and e.get("combo_id") != c_id]
                    pedido["total"] -= pr; cliente.paso_actual = "CONFIRMACION"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                    return self._enviar_resumen(wa_id, pedido)
                elif inter_id == "edit_combo_soda":
                    pedido["extras"] = [e for e in pedido["extras"] if not (isinstance(e, dict) and e.get("combo_id") == c_id and e.get("tipo") == "soda_combo")]
                    pedido["combo_id_actual"] = c_id; pedido["editando_item"] = True
                    cliente.paso_actual = "COMBO_SODA"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                    return self._enviar_sodas(wa_id, "Cambia el sabor de tu **Soda**:")
                elif inter_id.startswith("edit_combo_pz_"):
                    idx_c = int(inter_id.split("_")[-1])
                    pzs_c = [(i, p) for i, p in enumerate(pedido["pizzas"]) if p.get("combo_id") == c_id]
                    if pzs_c:
                        ri, pd = pzs_c[idx_c]; pedido["total"] -= (20 if "Boneless" in pd["nombre"] else 0)
                        pedido["pizzas"].pop(ri); pedido["pizzas_por_configurar"] = 1; pedido["tamano_actual"] = pd["tamano"]
                        pedido["combo_id_actual"] = c_id; pedido["combo_activo"] = "si"; pedido["editando_item"] = True
                        cliente.paso_actual = "PIZZA_MODO"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                        return self.wa.enviar_botones(wa_id, f"Re-configura la pizza:", [{"id":"modo_full","title":"🍕 Completa"},{"id":"modo_mitad","title":"🌗 Mitad y Mitad"}])

            # --- CIERRE ---
            if inter_id == "pagar":
                cliente.paso_actual = "CONFIRMACION"; db.session.commit(); return self._enviar_resumen(wa_id, pedido)
            elif paso == "CONFIRMACION":
                if inter_id == "ok_pedido":
                    cliente.paso_actual = "ENTREGA"; db.session.commit()
                    return self.wa.enviar_botones(wa_id, "¿Cómo recibes?", [{"id":"dom","title":"🛵 Domicilio"},{"id":"rec","title":"🛍️ Recoger"}])
            elif paso == "ENTREGA":
                pedido["tipo_entrega"] = "domicilio" if inter_id == "dom" else "recoger"
                cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                if inter_id == "rec": return self._finalizar_orden(wa_id, cliente, pedido)
                df = f"{cliente.calle} #{cliente.numero}, {cliente.cruzamientos} ({cliente.referencia})"
                cliente.paso_actual = "CONFIRMAR_DIR"; db.session.commit()
                return self.wa.enviar_botones(wa_id, f"📍 ¿Enviar aquí?\n_{df}_", [{"id":"dir_si","title":"✅ Sí"},{"id":"dir_no","title":"✏️ Otra"}])
            elif paso == "CONFIRMAR_DIR":
                if inter_id == "dir_si":
                    pedido["direccion"] = f"{cliente.calle} #{cliente.numero}, {cliente.cruzamientos} ({cliente.referencia})"
                    return self._finalizar_orden(wa_id, cliente, pedido)
                cliente.paso_actual = "DIR_NUEVA"; db.session.commit()
                return self.wa.enviar_texto(wa_id, "Dime la **nueva dirección** completa:")
            elif paso == "DIR_NUEVA":
                pedido["direccion"] = texto; return self._finalizar_orden(wa_id, cliente, pedido)

        except Exception as e: print(f"❌ ERROR BOT: {e}", flush=True)

    # --- LÓGICA PRECIOS ---
    def _procesar_seleccion_sabor(self, wa_id, cliente, pedido, nombre_sabor, ingredientes):
        modo, tam, c_id = pedido.get("modo_actual"), pedido.get("tamano_actual", "grande"), pedido.get("combo_id_actual")
        p_pz = 0
        if modo == "modo_full":
            if not pedido.get("combo_activo"):
                p_pz = MENU_PIZZAS_BONELESS[tam] if "Boneless" in nombre_sabor else MENU_PIZZAS[tam]; pedido["total"] += p_pz
            elif "Boneless" in nombre_sabor: p_pz = 20; pedido["total"] += 20
            pedido["pizzas"].append({"nombre": f"Completa {nombre_sabor}", "ingredientes": ingredientes, "tamano": tam, "precio": p_pz, "combo_id": c_id})
            return self._verificar_siguiente_paso(wa_id, cliente, pedido)
        elif modo == "modo_mitad":
            if "mitad_a" not in pedido:
                pedido["mitad_a"] = {"nombre": nombre_sabor, "ingredientes": ingredientes}
                cliente.paso_actual = "PIZZA_TIPO_ELECCION"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                return self.wa.enviar_botones(wa_id, "Sabor para la otra mitad:", [{"id":"tipo_esp","title":"🌟 Especialidad"},{"id":"tipo_ing","title":"👨‍🍳 Armarla"}])
            else:
                m_a, m_b = pedido.pop("mitad_a"), {"nombre": nombre_sabor, "ingredientes": ingredientes}
                has_bl = "Boneless" in m_a["nombre"] or "Boneless" in m_b["nombre"]
                if not pedido.get("combo_activo"):
                    if "Boneless" in m_a["nombre"] and "Boneless" in m_b["nombre"]: p_pz = MENU_PIZZAS_BONELESS[tam]
                    elif has_bl: p_pz = MENU_PIZZAS[tam] + 20
                    else: p_pz = MENU_PIZZAS[tam]
                    pedido["total"] += p_pz
                elif has_bl: p_pz = 20; pedido["total"] += 20
                pedido["pizzas"].append({"nombre": f"Mitad {m_a['nombre']} / {m_b['nombre']}", "ingredientes": m_a["ingredientes"]+m_b["ingredientes"], "tamano": tam, "precio": p_pz, "combo_id": c_id})
                return self._verificar_siguiente_paso(wa_id, cliente, pedido)

    def _verificar_siguiente_paso(self, wa_id, cliente, pedido):
        if pedido.pop("editando_item", False):
            pedido.pop("combo_activo", None); pedido.pop("combo_id_actual", None); pedido.pop("modo_actual", None)
            cliente.paso_actual = "CONFIRMACION"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
            return self._enviar_resumen(wa_id, pedido)
        pedido["pizzas_por_configurar"] -= 1; pedido.pop("modo_actual", None)
        if pedido["pizzas_por_configurar"] > 0:
            cliente.paso_actual = "PIZZA_MODO"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
            return self.wa.enviar_botones(wa_id, "Pizza lista. Configura la *Siguiente Pizza*:", [{"id":"modo_full","title":"🍕 Completa"},{"id":"modo_mitad","title":"🌗 Mitad y Mitad"}])
        pedido.pop("combo_id_actual", None); pedido.pop("combo_activo", None)
        cliente.paso_actual = "MENU_PRINCIPAL"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
        return self.wa.enviar_botones(wa_id, f"✅ Agregado. Total: *${pedido['total']}*", [{"id":"hola","title":"🥤 Menú"},{"id":"pagar","title":"💳 Pagar"}])

    # --- ENVÍOS ---
    def _enviar_menu_principal(self, wa_id, cliente):
        total = json.loads(cliente.pedido_temporal).get("total", 0)
        sections = [{"title": "Paquetes", "rows": [{"id":"combo_grande","title":"🎁 Combo Grande $300", "description": "2 Gdes + Ensalada + Soda 2L"},{"id":"combo_familiar","title":"🎁 Combo Familiar $370", "description": "2 Fam + Espaguetti + Soda 2L"}]},{"title": "Individuales", "rows": [{"id":"cat_pizzas","title":"🍕 Arma tu Pizza"}]},{"title": "Snacks", "rows": [{"id":k, "title":k.replace('_',' ').capitalize(), "description":f"${v}"} for k,v in MENU_SNACKS.items()]}]
        return self.wa.enviar_lista(wa_id, "Mr. Bigo's Pizza", f"¡Hola {cliente.nombre}! 👋", f"Total: ${total}", "Ver Menú", sections)

    def _enviar_resumen(self, wa_id, pedido):
        res = "📋 *REVISIÓN DE TU PEDIDO*\n\n"
        for i, p in enumerate(pedido["pizzas"]): res += f"{'📦' if p.get('combo_id') else '🍕'} *P{i+1}:* {p['nombre']}\n"
        for ex in pedido["extras"]:
            name = ex['nombre'] if isinstance(ex, dict) else ex
            if "(Combo)" in name and (isinstance(ex, str) or ex.get('precio', 0) == 0): continue
            res += f"{'🔸' if (isinstance(ex, dict) and ex.get('combo_id')) else '🥤'} *{name}*\n"
        res += f"\n💵 *TOTAL FINAL: ${pedido['total']}*"
        return self.wa.enviar_botones(wa_id, res, [{"id":"ok_pedido","title":"✅ Confirmar"},{"id":"modificar_pedido","title":"✏️ Editar"},{"id":"cancel_pedido","title":"❌ Reiniciar"}])

    def _enviar_lista_edicion(self, wa_id, pedido):
        rows = []; cv = []
        for ex in pedido["extras"]:
            if isinstance(ex, dict) and ex.get("combo_id") and ex.get("combo_id") not in cv:
                rows.append({"id": f"combo_edit_{ex['combo_id']}", "title": "Gestionar Paquete", "description": "Editar/Borrar combo."}); cv.append(ex['combo_id'])
        for i, pz in enumerate(pedido["pizzas"]):
            if not pz.get("combo_id"): rows.append({"id": f"del_pz_{i}", "title": "Borrar Pizza", "description": pz['nombre'][:70]})
        for i, ex in enumerate(pedido["extras"]):
            if isinstance(ex, dict) and not ex.get("combo_id"): rows.append({"id": f"del_ex_{i}", "title": "Quitar Snack", "description": ex['nombre'][:70]})
        return self.wa.enviar_lista(wa_id, "Editar", "Toca qué gestionar:", "Bigo's", "Ver Carrito", [{"title":"Tu Orden", "rows":rows}])

    def _enviar_lista_componentes_combo(self, wa_id, pedido, c_id):
        rows = []
        for e in pedido["extras"]:
            if isinstance(e, dict) and e.get("combo_id") == c_id and e.get("tipo") == "soda_combo":
                rows.append({"id": "edit_combo_soda", "title": "Cambiar Soda", "description": f"Actual: {e['nombre']}"})
        pzs_c = [p for p in pedido["pizzas"] if p.get("combo_id") == c_id]
        for i, p in enumerate(pzs_c): rows.append({"id": f"edit_combo_pz_{i}", "title": f"Cambiar Pizza {i+1}", "description": p['nombre']})
        rows.append({"id": "del_combo_total", "title": "🗑️ Eliminar Todo", "description": "Borrar paquete completo."})
        return self.wa.enviar_lista(wa_id, "Combo", "Modificar:", "Bigo's", "Opciones", [{"title":"Detalle", "rows":rows}])

    def _enviar_confirmacion_item(self, wa_id, item, total):
        return self.wa.enviar_botones(wa_id, f"✅ *{item}* añadido.\n💰 Total: *${total}*", [{"id":"hola","title":"🥤 Menú"},{"id":"pagar","title":"💳 Pagar"}])

    def _enviar_sodas(self, wa_id, bt):
        rows = [{"id": s, "title": s} for s in SODA_SABORES]
        return self.wa.enviar_lista(wa_id, "Bebidas", bt, "Bigo's", "Lista", [{"title":"Sodas", "rows":rows}])

    def _enviar_especialidades(self, wa_id):
        rows = [{"id": f"esp_{k.lower().replace(' ', '_')}", "title": k, "description": ", ".join(v)[:70]} for k, v in ESPECIALIDADES.items()]
        return self.wa.enviar_lista(wa_id, "Sabor", "Elige:", "Bigo's", "Lista", [{"title":"Sabores", "rows":rows}])

    def _enviar_tamanos(self, wa_id):
        rows = [{"id": k, "title": k.capitalize(), "description": f"Desde ${v}"} for k, v in MENU_PIZZAS.items()]
        return self.wa.enviar_lista(wa_id, "Tamaños", "Elige:", "Bigo's", "Lista", [{"title":"Pizzas", "rows":rows}])

    def _enviar_salsas(self, wa_id):
        rows = [{"id": s, "title": s} for s in SALSAS]; return self.wa.enviar_lista(wa_id, "Salsas", "Elige:", "Bigo's", "Lista", [{"title":"Salsas", "rows":rows}])

    def _enviar_papas(self, wa_id):
        rows = [{"id": p, "title": p} for p in TIPOS_PAPAS]; return self.wa.enviar_lista(wa_id, "Papas", "Estilo:", "Bigo's", "Lista", [{"title":"Tipos", "rows":rows}])

    def _enviar_ingredientes(self, wa_id, lista, nc, pr):
        rows = [{"id": f"ing_{pr}_{i}", "title": ing} for i, ing in enumerate(lista)]
        return self.wa.enviar_lista(wa_id, f"Lista: {nc}", "Selecciona:", "Bigo's", "Ver Lista", [{"title":nc, "rows":rows}])

    def _finalizar_orden(self, wa_id, cliente, pedido):
        p = Pedido(cliente_id=cliente.id, total=pedido["total"], detalles_json=json.dumps(pedido), tipo_entrega=pedido["tipo_entrega"])
        db.session.add(p); cliente.paso_actual = "INICIO"; db.session.commit()
        return self.wa.enviar_texto(wa_id, f"🧾 *ORDEN REALIZADA #{p.id}*\n💰 Total: *${pedido['total']}*\n¡Gracias!")