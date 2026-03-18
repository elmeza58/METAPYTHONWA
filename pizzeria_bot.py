#/Users/alejandromeza/WA_BOT_PROJECTN/pizzeria_bot.py
from models import db, Cliente, Pedido
import json

# --- DATA MR. BIGO'S ---
MENU_PIZZAS = {"familiar": 170, "grande": 150, "mediana": 130}
MENU_PIZZAS_BONELESS = {"familiar": 250, "grande": 210} # Precios especiales Boneless
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
    "Boneless": ["Boneless", "Salsa a elegir"] # Nueva especialidad
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
                cliente = Cliente(telefono=wa_id, paso_actual="INICIO")
                db.session.add(cliente); db.session.commit()

            if (texto.lower() == "hola" and inter_id is None) or inter_id == "hola":
                cliente.paso_actual = "MENU_PRINCIPAL"
                cliente.pedido_temporal = json.dumps({"pizzas": [], "extras": [], "total": 0})
                db.session.commit()
                return self._enviar_menu_principal(wa_id, 0)

            pedido = json.loads(cliente.pedido_temporal)
            paso = cliente.paso_actual

            # --- MÁQUINA DE ESTADOS ---
            if paso == "MENU_PRINCIPAL":
                if inter_id == "cat_pizzas":
                    cliente.paso_actual = "PIZZA_TAMANO"; db.session.commit()
                    return self._enviar_tamanos(wa_id)
                elif inter_id in MENU_COMBOS:
                    pedido["total"] += MENU_COMBOS[inter_id]; pedido["pizzas_por_configurar"] = 2
                    cliente.paso_actual = "PIZZA_MODO"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                    return self.wa.enviar_botones(wa_id, "Configura la *Pizza 1*:", [{"id":"modo_full","title":"🍕 Completa"},{"id":"modo_mitad","title":"🌗 Mitad y Mitad"}])
                elif inter_id in MENU_SNACKS:
                    pedido["item_en_proceso"] = inter_id
                    cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                    if "boneless" in inter_id or inter_id == "alitas":
                        cliente.paso_actual = "SNACK_SALSA"; db.session.commit()
                        return self._enviar_salsas(wa_id)
                    elif inter_id == "crazy_papas":
                        cliente.paso_actual = "SNACK_PAPA"; db.session.commit()
                        return self._enviar_papas(wa_id)
                    else:
                        pedido["extras"].append(inter_id.replace('_',' ').capitalize())
                        pedido["total"] += MENU_SNACKS[inter_id]; pedido.pop("item_en_proceso", None)
                        cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                        return self.wa.enviar_botones(wa_id, f"✅ Añadido. Total: ${pedido['total']}", [{"id":"hola","title":"Ver Menú"},{"id":"pagar","title":"Pagar"}])

            elif paso == "PIZZA_TAMANO":
                if inter_id in MENU_PIZZAS:
                    pedido["tamano_actual"] = inter_id; pedido["pizzas_por_configurar"] = 1
                    cliente.paso_actual = "PIZZA_MODO"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                    return self.wa.enviar_botones(wa_id, f"Pizza {inter_id.capitalize()}.\n¿Cómo la quieres?", [{"id":"modo_full","title":"🍕 Completa"},{"id":"modo_mitad","title":"🌗 Mitad y Mitad"}])

            elif paso == "PIZZA_MODO":
                pedido["modo_actual"] = inter_id
                cliente.paso_actual = "PIZZA_TIPO_ELECCION"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                prompt = "Elige el sabor:" if inter_id == "modo_full" else "Elige el sabor de la *Primera Mitad*:"
                return self.wa.enviar_botones(wa_id, prompt, [{"id":"tipo_esp","title":"🌟 Especialidad"},{"id":"tipo_ing","title":"👨‍🍳 Armarla"}])

            elif paso == "PIZZA_TIPO_ELECCION":
                if inter_id == "tipo_esp": return self._enviar_especialidades(wa_id)
                elif inter_id == "tipo_ing":
                    cliente.paso_actual = "PIZZA_INGREDIENTES"; db.session.commit()
                    return self.wa.enviar_botones(wa_id, "Categoría de ingredientes:", [{"id":"cat_prot","title":"🥩 Proteínas"},{"id":"cat_veg","title":"🌿 Vegetales"}])

            elif paso == "PIZZA_ESPECIALIDAD":
                if inter_id.startswith("esp_"):
                    nombre_esp = inter_id.split("_")[1].replace("_", " ").title()
                    if nombre_esp == "Boneless":
                        pedido["sabor_en_espera"] = "Boneless"; cliente.paso_actual = "PIZZA_SALSA_BONELESS"
                        cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                        return self._enviar_salsas(wa_id)
                    return self._procesar_seleccion_sabor(wa_id, cliente, pedido, nombre_esp, ESPECIALIDADES[nombre_esp])

            elif paso == "PIZZA_SALSA_BONELESS":
                if inter_id in SALSAS:
                    sabor = f"Boneless ({inter_id})"
                    return self._procesar_seleccion_sabor(wa_id, cliente, pedido, sabor, ["Boneless", inter_id])

            elif paso == "PIZZA_INGREDIENTES":
                if inter_id == "cat_prot": return self._enviar_ingredientes(wa_id, INGREDIENTES_PROT, "Proteínas", "prot")
                elif inter_id == "cat_veg": return self._enviar_ingredientes(wa_id, INGREDIENTES_VEG, "Vegetales", "veg")
                elif inter_id and ("_prot_" in inter_id or "_veg_" in inter_id):
                    tipo, idx = inter_id.split("_")[1], int(inter_id.split("_")[2])
                    ing = INGREDIENTES_PROT[idx] if tipo == "prot" else INGREDIENTES_VEG[idx]
                    if "armando" not in pedido: pedido["armando"] = []
                    if ing not in pedido["armando"]:
                        pedido["armando"].append(ing)
                        if len(pedido["armando"]) > 5: pedido["total"] += 20
                    cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                    return self.wa.enviar_botones(wa_id, f"✅ {ing} añadido.\n📝 Llevas: {', '.join(pedido['armando'])}", [{"id":"cat_prot","title":"🥩 Proteínas"},{"id":"cat_veg","title":"🌿 Vegetales"},{"id":"fin_pizza","title":"🏁 Terminar"}])
                elif inter_id == "fin_pizza":
                    return self._procesar_seleccion_sabor(wa_id, cliente, pedido, "Armada", pedido.pop("armando", []))

            # --- CONFIRMACIÓN Y PAGO ---
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
                cliente.paso_actual = "DIRECCION"; db.session.commit()
                return self.wa.enviar_texto(wa_id, "📍 Escribe tu dirección completa:")

            elif paso == "DIRECCION":
                pedido["direccion"] = texto; return self._finalizar_orden(wa_id, cliente, pedido)

        except Exception as e:
            print(f"❌ ERROR BOT: {e}", flush=True)

    # --- LÓGICA DE PRECIOS Y MITADES ---
    def _procesar_seleccion_sabor(self, wa_id, cliente, pedido, nombre_sabor, ingredientes):
        modo = pedido.get("modo_actual")
        
        if modo == "modo_full":
            # Precio base según si es Boneless o Normal
            tam = pedido["tamano_actual"]
            precio = MENU_PIZZAS_BONELESS[tam] if "Boneless" in nombre_sabor else MENU_PIZZAS[tam]
            pedido["total"] += precio
            pedido["pizzas"].append({"nombre": f"Completa {nombre_sabor}", "ingredientes": ingredientes, "tamano": tam})
            return self._verificar_siguiente_paso(wa_id, cliente, pedido)
            
        elif modo == "modo_mitad":
            if "mitad_a" not in pedido:
                pedido["mitad_a"] = {"nombre": nombre_sabor, "ingredientes": ingredientes}
                cliente.paso_actual = "PIZZA_TIPO_ELECCION"
                cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
                return self.wa.enviar_botones(wa_id, "¡Primera mitad lista! Elige el sabor de la *Segunda Mitad*:", [{"id":"tipo_esp","title":"🌟 Especialidad"},{"id":"tipo_ing","title":"👨‍🍳 Armarla"}])
            else:
                # Ya tenemos ambas mitades, calculamos precio
                tam = pedido["tamano_actual"]
                m_a = pedido.pop("mitad_a")
                m_b = {"nombre": nombre_sabor, "ingredientes": ingredientes}
                
                # REGLA: Si alguna mitad es Boneless, se usa precio base de pizza normal + $20 extra
                # O si es 100% boneless se usa precio boneless. 
                # El usuario pidió: "mitad boneless y mitad otra especialidad sube 20 pesos".
                has_boneless = "Boneless" in m_a["nombre"] or "Boneless" in m_b["nombre"]
                
                if "Boneless" in m_a["nombre"] and "Boneless" in m_b["nombre"]:
                    precio = MENU_PIZZAS_BONELESS[tam]
                elif has_boneless:
                    precio = MENU_PIZZAS[tam] + 20
                else:
                    precio = MENU_PIZZAS[tam]
                
                pedido["total"] += precio
                pedido["pizzas"].append({
                    "nombre": f"Mitad {m_a['nombre']} / Mitad {m_b['nombre']}",
                    "ingredientes": m_a["ingredientes"] + m_b["ingredientes"],
                    "tamano": tam
                })
                return self._verificar_siguiente_paso(wa_id, cliente, pedido)

    # --- AUXILIARES ---
    def _verificar_siguiente_paso(self, wa_id, cliente, pedido):
        pedido["pizzas_por_configurar"] -= 1
        pedido.pop("modo_actual", None)
        if pedido["pizzas_por_configurar"] > 0:
            cliente.paso_actual = "PIZZA_MODO"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
            return self.wa.enviar_botones(wa_id, f"¡Pizza lista! Configuremos la *Siguiente Pizza* del combo.\n💰 Total: *${pedido['total']}*", [{"id":"modo_full","title":"🍕 Completa"},{"id":"modo_mitad","title":"🌗 Mitad y Mitad"}])
        
        cliente.paso_actual = "MENU_PRINCIPAL"; cliente.pedido_temporal = json.dumps(pedido); db.session.commit()
        return self.wa.enviar_botones(wa_id, f"✅ Agregado. Total actual: *${pedido['total']}*", [{"id":"hola","title":"🥤 Ver Menú"},{"id":"pagar","title":"💳 Pagar"}])

    def _enviar_resumen(self, wa_id, pedido):
        res = "📋 *REVISIÓN DE TU PEDIDO*\n\n"
        for i, p in enumerate(pedido["pizzas"]):
            res += f"🍕 *P{i+1} ({p['tamano']}):* {p['nombre']}\n"
        if pedido["extras"]: res += f"\n🥤 *Extras:* {', '.join(pedido['extras'])}\n"
        res += f"\n💵 *TOTAL FINAL: ${pedido['total']}*"
        return self.wa.enviar_botones(wa_id, res, [{"id":"ok_pedido","title":"✅ Todo correcto"},{"id":"cancel_pedido","title":"❌ Reiniciar"}])

    def _enviar_menu_principal(self, wa_id, total):
        sections = [{"title": "Pizzas", "rows": [{"id":"cat_pizzas","title":"🍕 Arma tu Pizza"},{"id":"combo_grande","title":"🎁 Combo Grande $300"},{"id":"combo_familiar","title":"🎁 Combo Familiar $370"}]},{"title": "Snacks", "rows": [{"id":k, "title":k.replace('_',' ').capitalize(), "description":f"${v}"} for k,v in MENU_SNACKS.items()]}]
        return self.wa.enviar_lista(wa_id, "Mr. Bigo's Pizza", "Elige una opción:", f"Total: ${total}", "Ver Menú", sections)

    def _enviar_especialidades(self, wa_id):
        cliente = Cliente.query.filter_by(telefono=wa_id).first(); cliente.paso_actual = "PIZZA_ESPECIALIDAD"; db.session.commit()
        rows = []
        for k, v in ESPECIALIDADES.items():
            desc = ", ".join(v); desc = desc[:68] + "..." if len(desc) > 72 else desc
            rows.append({"id": f"esp_{k.lower().replace(' ', '_')}", "title": k, "description": desc})
        return self.wa.enviar_lista(wa_id, "Especialidades", "Elige el sabor:", "Bigo's", "Ver Sabores", [{"title":"Especialidades", "rows":rows}])

    def _enviar_tamanos(self, wa_id):
        rows = [{"id": k, "title": k.capitalize(), "description": f"Desde ${v}"} for k, v in MENU_PIZZAS.items()]
        return self.wa.enviar_lista(wa_id, "Tamaños", "Elige tamaño:", "Bigo's", "Seleccionar", [{"title":"Pizzas", "rows":rows}])

    def _enviar_salsas(self, wa_id):
        rows = [{"id": s, "title": s} for s in SALSAS]
        return self.wa.enviar_lista(wa_id, "Salsas", "Elige la salsa:", "Mr. Bigo's", "Salsas", [{"title":"Salsas", "rows":rows}])

    def _enviar_papas(self, wa_id):
        rows = [{"id": p, "title": p} for p in TIPOS_PAPAS]
        return self.wa.enviar_lista(wa_id, "Estilo de Papas", "Elige:", "Bigo's", "Papas", [{"title":"Papas", "rows":rows}])

    def _enviar_ingredientes(self, wa_id, lista, nombre_cat, prefijo):
        rows = [{"id": f"ing_{prefijo}_{i}", "title": ing} for i, ing in enumerate(lista)]
        return self.wa.enviar_lista(wa_id, f"Lista: {nombre_cat}", "Selecciona:", "Bigo's", "Ver Lista", [{"title":nombre_cat, "rows":rows}])

    def _finalizar_orden(self, wa_id, cliente, pedido):
        p = Pedido(cliente_id=cliente.id, total=pedido["total"], detalles_json=json.dumps(pedido), tipo_entrega=pedido["tipo_entrega"])
        db.session.add(p); cliente.paso_actual = "INICIO"; db.session.commit()
        return self.wa.enviar_texto(wa_id, f"🧾 *ORDEN REALIZADA #{p.id}*\n💰 Total: *${pedido['total']}*\n¡Gracias por elegir Mr. Bigo's!")