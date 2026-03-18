# /Users/alejandromeza/WA_BOT_PROJECTN/pizzeria_bot.py
from models import db, Cliente, Pedido
import json
import uuid # Para generar IDs únicos para cada combo

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
            if wa_id.startswith("521"): wa_id = "52" + wa_id[3:]
            cliente = Cliente.query.filter_by(telefono=wa_id).first()
            
            # --- 1. REGISTRO DE CLIENTES ---
            if not cliente:
                cliente = Cliente(telefono=wa_id, paso_actual="REG_NOMBRE")
                db.session.add(cliente); db.session.commit()
                return self.wa.enviar_texto(wa_id, "¡Hola! Bienvenido a *Mr. Bigo's Pizza*. 🍕\n¿Cuál es tu **Nombre**?")

            paso = cliente.paso_actual

            # --- 2. BLOQUE DE REGISTRO ---
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
                    return self.wa.enviar_texto(wa_id, "¿Número de casa?")
                elif paso == "REG_NUMERO":
                    cliente.numero = texto.strip()
                    cliente.paso_actual = "REG_CRUCES"; db.session.commit()
                    return self.wa.enviar_texto(wa_id, "¿Cruzamientos?")
                elif paso == "REG_CRUCES":
                    cliente.cruzamientos = texto.strip()
                    cliente.paso_actual = "REG_REF"; db.session.commit()
                    return self.wa.enviar_texto(wa_id, "Una **Referencia** visual:")
                elif paso == "REG_REF":
                    cliente.referencia = texto.strip()
                    cliente.paso_actual = "MENU_PRINCIPAL"; db.session.commit()
                    return self.wa.enviar_botones(wa_id, "¡Registro completado! ✅", [{"id":"hola","title":"Ver Menú"}])

            # --- 3. NAVEGACIÓN ---
            if (texto.lower() == "hola" and inter_id is None) or inter_id == "hola":
                cliente.paso_actual = "MENU_PRINCIPAL"
                if inter_id is None: cliente.pedido_temporal = json.dumps({"pizzas": [], "extras": [], "total": 0})
                db.session.commit()
                return self._enviar_menu_principal(wa_id, cliente)

            pedido = json.loads(cliente.pedido_temporal)

            # --- 4. MÁQUINA DE ESTADOS DEL PEDIDO ---
            if paso == "MENU_PRINCIPAL":
                if inter_id == "cat_pizzas":
                    cliente.paso_actual = "PIZZA_TAMANO"; db.session.commit()
                    return self._enviar_tamanos(wa_id)
                
                elif inter_id in MENU_COMBOS:
                    # Generamos un ID único para este combo para agrupar sus pizzas y extras
                    c_id = str(uuid.uuid4())[:8]
                    pedido["total"] += MENU_COMBOS[inter_id]
                    pedido["pizzas_por_configurar"] = 2
                    pedido["tamano_actual"] = "grande" if inter_id == "combo_grande" else "familiar"
                    pedido["combo_activo"] = inter_id
                    pedido["combo_id_actual"] = c_id
                    
                    snack = "Ensalada" if inter_id == "combo_grande" else "Espaguetti"
                    # Marcamos los items con su combo_id
                    pedido["extras"].append({"nombre": f"{snack} (Combo)", "precio": 0, "combo_id": c_id})
                    
                    cliente.paso_actual = "COMBO_SODA"
                    cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                    return self._enviar_sodas(wa_id, f"🎁 *Paquete {pedido['tamano_actual'].capitalize()}*.\nIncluye 2 Pizzas, 1 {snack} y 1 Soda.\nElige sabor de **Soda**:")

                elif inter_id in MENU_SNACKS:
                    pedido["item_en_proceso"] = inter_id
                    cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                    if "boneless" in inter_id or inter_id == "alitas":
                        cliente.paso_actual = "SNACK_SALSA"; db.session.commit(); return self._enviar_salsas(wa_id)
                    elif inter_id == "crazy_papas":
                        cliente.paso_actual = "SNACK_PAPA"; db.session.commit(); return self._enviar_papas(wa_id)
                    else:
                        n, p = inter_id.replace('_',' ').capitalize(), MENU_SNACKS[inter_id]
                        pedido["extras"].append({"nombre": n, "precio": p, "combo_id": None})
                        pedido["total"] += p; pedido.pop("item_en_proceso", None)
                        cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                        return self.wa.enviar_botones(wa_id, f"✅ {n} añadido.", [{"id":"hola","title":"Menú"},{"id":"pagar","title":"Pagar"}])

            elif paso == "COMBO_SODA":
                if inter_id in SODA_SABORES:
                    c_id = pedido.get("combo_id_actual")
                    pedido["extras"].append({"nombre": f"Soda {inter_id} (Combo)", "precio": 0, "combo_id": c_id})
                    cliente.paso_actual = "PIZZA_MODO"
                    cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                    return self.wa.enviar_botones(wa_id, f"✅ Soda {inter_id} elegida.\nConfiguremos la *Pizza 1*:", [{"id":"modo_full","title":"🍕 Completa"},{"id":"modo_mitad","title":"🌗 Mitad y Mitad"}])

            elif paso == "SNACK_SALSA":
                if inter_id in SALSAS:
                    item = pedido.pop("item_en_proceso", "Snack")
                    n, p = f"{item.capitalize()} ({inter_id})", MENU_SNACKS.get(item, 0)
                    pedido["extras"].append({"nombre": n, "precio": p, "combo_id": None})
                    pedido["total"] += p
                    cliente.paso_actual = "MENU_PRINCIPAL"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                    return self.wa.enviar_botones(wa_id, f"✅ Añadido. Total: ${pedido['total']}", [{"id":"hola","title":"Menú"},{"id":"pagar","title":"Pagar"}])

            elif paso == "SNACK_PAPA":
                if inter_id in TIPOS_PAPAS:
                    pedido.pop("item_en_proceso", "crazy_papas")
                    n, p = f"Crazy Papas {inter_id}", 85
                    pedido["extras"].append({"nombre": n, "precio": p, "combo_id": None})
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
                    return self.wa.enviar_botones(wa_id, "Ingredientes (5 gratis):", [{"id":"cat_prot","title":"🥩 Prot"},{"id":"cat_veg","title":"🌿 Veg"}])

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
                    aviso = "\n\n⚠️ El 6to cuesta $20." if cant == 5 else ""
                    return self.wa.enviar_botones(wa_id, f"✅ {ing} ({cant}/5).{aviso}\n📝 Llevas: {', '.join(pedido['armando'])}", [{"id":"cat_prot","title":"🥩 Prot"},{"id":"cat_veg","title":"🌿 Veg"},{"id":"fin_pizza","title":"🏁 Terminar"}])
                elif inter_id == "fin_pizza":
                    return self._procesar_seleccion_sabor(wa_id, cliente, pedido, "Armada", pedido.pop("armando", []))

            elif paso == "PIZZA_ESPECIALIDAD":
                if inter_id.startswith("esp_"):
                    nombre_esp = inter_id[4:].replace("_", " ").title()
                    if nombre_esp == "Boneless":
                        cliente.paso_actual = "PIZZA_SALSA_BONELESS"; db.session.commit(); return self._enviar_salsas(wa_id)
                    return self._procesar_seleccion_sabor(wa_id, cliente, pedido, nombre_esp, ESPECIALIDADES.get(nombre_esp, []))

            elif paso == "PIZZA_SALSA_BONELESS":
                if inter_id in SALSAS:
                    return self._procesar_seleccion_sabor(wa_id, cliente, pedido, f"Boneless ({inter_id})", ["Boneless", inter_id])

            # --- 5. GESTIÓN DE EDICIÓN Y BORRADO (CORREGIDO) ---
            if inter_id == "modificar_pedido":
                cliente.paso_actual = "MODIFICAR_CARRITO"; db.session.commit(); return self._enviar_lista_edicion(wa_id, pedido)
            
            elif paso == "MODIFICAR_CARRITO":
                # Si el usuario eligió un combo para editar
                if inter_id.startswith("combo_edit_"):
                    c_id = inter_id.replace("combo_edit_", "")
                    pedido["combo_a_gestionar"] = c_id
                    cliente.paso_actual = "DECISION_COMBO"; db.session.commit()
                    return self.wa.enviar_botones(wa_id, "¿Qué deseas hacer con este Paquete?", 
                                               [{"id":"reconf_combo","title":"✏️ Re-configurar"},{"id":"del_combo","title":"🗑️ Eliminar Todo"}])
                
                # Borrado directo para pizzas/items individuales (sin combo_id)
                elif inter_id.startswith("del_pz_"):
                    idx = int(inter_id.split("_")[-1])
                    pz = pedido["pizzas"].pop(idx); pedido["total"] -= pz.get("precio", 0)
                elif inter_id.startswith("del_ex_"):
                    idx = int(inter_id.split("_")[-1])
                    ex = pedido["extras"].pop(idx); pedido["total"] -= ex.get("precio", 0)
                
                cliente.paso_actual = "CONFIRMACION"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                return self._enviar_resumen(wa_id, pedido)

            elif paso == "DECISION_COMBO":
                c_id = pedido.pop("combo_a_gestionar")
                # Buscamos el precio del combo para ajustarlo si se borra
                # Nota: El precio está en el item del extra que guardamos al inicio
                combo_precio = 0
                for ex in pedido["extras"]:
                    if ex.get("combo_id") == c_id:
                        # Buscamos el tipo de combo para saber su precio base
                        if "Grande" in ex["nombre"]: combo_precio = 300
                        if "Familiar" in ex["nombre"]: combo_precio = 370

                if inter_id == "del_combo":
                    # Borrar todo lo que tenga ese combo_id
                    pedido["pizzas"] = [p for p in pedido["pizzas"] if p.get("combo_id") != c_id]
                    pedido["extras"] = [e for e in pedido["extras"] if e.get("combo_id") != c_id]
                    pedido["total"] -= combo_precio
                    # Limpiar si quedaron remanentes de boneless extra en ese combo
                    cliente.paso_actual = "CONFIRMACION"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                    return self._enviar_resumen(wa_id, pedido)
                
                elif inter_id == "reconf_combo":
                    # Borrar items viejos pero NO el precio (porque lo volverá a configurar)
                    pedido["pizzas"] = [p for p in pedido["pizzas"] if p.get("combo_id") != c_id]
                    pedido["extras"] = [e for e in pedido["extras"] if e.get("combo_id") != c_id]
                    pedido["total"] -= combo_precio # Lo restamos para que al re-elegir el combo se sume de nuevo limpio
                    # Simulamos que vuelve a elegir el combo (esto reinicia el flujo completo del combo)
                    # Para simplificar: lo mandamos al menú para que lo elija de nuevo o implementamos el salto
                    cliente.paso_actual = "MENU_PRINCIPAL"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                    return self.wa.enviar_texto(wa_id, "Paquete removido. Por favor elígelo de nuevo para configurar sus opciones:")

            # --- 6. BLOQUE DE CONFIRMACIÓN ---
            if inter_id == "pagar":
                cliente.paso_actual = "CONFIRMACION"; db.session.commit(); return self._enviar_resumen(wa_id, pedido)
            elif paso == "CONFIRMACION":
                if inter_id == "ok_pedido":
                    cliente.paso_actual = "ENTREGA"; db.session.commit()
                    return self.wa.enviar_botones(wa_id, "¿Cómo recibes tu orden?", [{"id":"dom","title":"🛵 Domicilio"},{"id":"rec","title":"🛍️ Recoger"}])
                elif inter_id == "cancel_pedido": return self.gestionar_pedido(wa_id, "hola", "hola")

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
                return self.wa.enviar_texto(wa_id, "Dime la **nueva dirección**:")
            elif paso == "DIR_NUEVA":
                pedido["direccion"] = texto; return self._finalizar_orden(wa_id, cliente, pedido)

        except Exception as e: print(f"❌ ERROR BOT: {e}", flush=True)

    # --- LÓGICA PRECIOS ---
    def _procesar_seleccion_sabor(self, wa_id, cliente, pedido, nombre_sabor, ingredientes):
        modo, tam = pedido.get("modo_actual"), pedido.get("tamano_actual", "grande")
        c_id = pedido.get("combo_id_actual")
        p_pz = 0
        if modo == "modo_full":
            if "combo_activo" not in pedido:
                p_pz = MENU_PIZZAS_BONELESS[tam] if "Boneless" in nombre_sabor else MENU_PIZZAS[tam]
                pedido["total"] += p_pz
            elif "Boneless" in nombre_sabor: p_pz = 20; pedido["total"] += 20
            pedido["pizzas"].append({"nombre": f"Completa {nombre_sabor}", "ingredientes": ingredientes, "tamano": tam, "precio": p_pz, "combo_id": c_id})
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
                pedido["pizzas"].append({"nombre": f"Mitad {m_a['nombre']} / {m_b['nombre']}", "ingredientes": m_a["ingredientes"]+m_b["ingredientes"], "tamano": tam, "precio": p_pz, "combo_id": c_id})
                return self._verificar_siguiente_paso(wa_id, cliente, pedido)

    def _verificar_siguiente_paso(self, wa_id, cliente, pedido):
        pedido["pizzas_por_configurar"] -= 1; pedido.pop("modo_actual", None)
        if pedido["pizzas_por_configurar"] > 0:
            cliente.paso_actual = "PIZZA_MODO"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
            return self.wa.enviar_botones(wa_id, f"Pizza 1 lista. Configura la *Pizza 2*:", [{"id":"modo_full","title":"🍕 Completa"},{"id":"modo_mitad","title":"🌗 Mitad y Mitad"}])
        
        # Limpiar combo_id_actual y combo_activo al terminar el combo
        pedido.pop("combo_id_actual", None); pedido.pop("combo_activo", None)
        cliente.paso_actual = "MENU_PRINCIPAL"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
        return self.wa.enviar_botones(wa_id, f"✅ Agregado. Total: *${pedido['total']}*", [{"id":"hola","title":"Menú"},{"id":"pagar","title":"Pagar"}])

    # --- ENVÍOS ---
    def _enviar_menu_principal(self, wa_id, cliente):
        total = json.loads(cliente.pedido_temporal).get("total", 0)
        sections = [{"title": "Paquetes", "rows": [{"id":"combo_grande","title":"🎁 Combo Grande $300", "description": "2 Gdes + Ensalada + Soda 2L"},{"id":"combo_familiar","title":"🎁 Combo Familiar $370", "description": "2 Fam + Espaguetti + Soda 2L"}]},{"title": "Individuales", "rows": [{"id":"cat_pizzas","title":"🍕 Armar Pizza"}]},{"title": "Snacks", "rows": [{"id":k, "title":k.replace('_',' ').capitalize(), "description":f"${v}"} for k,v in MENU_SNACKS.items()]}]
        return self.wa.enviar_lista(wa_id, "Mr. Bigo's Pizza", f"¡Hola {cliente.nombre}! 👋", f"Total: ${total}", "Ver Menú", sections)

    def _enviar_resumen(self, wa_id, pedido):
        res = "📋 *REVISIÓN DE TU PEDIDO*\n\n"
        for i, p in enumerate(pedido["pizzas"]): 
            tag = "📦" if p.get("combo_id") else "🍕"
            res += f"{tag} *P{i+1}:* {p['nombre']}\n"
        for ex in pedido["extras"]:
            tag = "🔸" if ex.get("combo_id") else "🥤"
            res += f"{tag} *{ex['nombre']}*\n"
        res += f"\n💵 *TOTAL FINAL: ${pedido['total']}*"
        return self.wa.enviar_botones(wa_id, res, [{"id":"ok_pedido","title":"✅ Confirmar"},{"id":"modificar_pedido","title":"✏️ Editar"},{"id":"cancel_pedido","title":"❌ Reiniciar"}])

    def _enviar_lista_edicion(self, wa_id, pedido):
        """Genera una lista inteligente: agrupa los componentes de un combo en una sola opción."""
        rows = []
        combos_vistos = []
        
        # Primero procesamos los paquetes (combos)
        # Buscamos en extras los nombres que contengan "(Combo)"
        for ex in pedido["extras"]:
            c_id = ex.get("combo_id")
            if c_id and c_id not in combos_vistos:
                rows.append({"id": f"combo_edit_{c_id}", "title": f"Gestionar Paquete", "description": f"Ver opciones de este combo."})
                combos_vistos.append(c_id)
        
        # Luego las pizzas individuales (que no tienen combo_id)
        for i, pz in enumerate(pedido["pizzas"]):
            if not pz.get("combo_id"):
                rows.append({"id": f"del_pz_{i}", "title": f"Quitar Pizza", "description": f"{pz['nombre'][:70]}"})
        
        # Luego los snacks individuales (que no tienen combo_id)
        for i, ex in enumerate(pedido["extras"]):
            if not ex.get("combo_id"):
                rows.append({"id": f"del_ex_{i}", "title": f"Quitar Snack", "description": f"{ex['nombre'][:70]}"})
                
        return self.wa.enviar_lista(wa_id, "Editar Carrito", "Selecciona el item a gestionar:", "Bigo's", "Ver Carrito", [{"title":"Tu Orden", "rows":rows}])

    def _enviar_sodas(self, wa_id, body_text):
        rows = [{"id": s, "title": s} for s in SODA_SABORES]
        return self.wa.enviar_lista(wa_id, "Bebidas", body_text, "Bigo's", "Ver Sabores", [{"title":"Sodas 2L", "rows":rows}])

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