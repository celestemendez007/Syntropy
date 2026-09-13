"""Session-based banking demo. Models and policy remain the financial authority.

SQLite isolates demo sessions and persists their messages, decisions and receipts.
The UI never submits amounts/dates: it confirms a server-issued offer and revision.
Dates are shifted from the synthetic snapshot to the current demo date; no model
features or research artifacts are changed.
"""
import copy
import json
import os
import re
import secrets
import sqlite3
import unicodedata
from datetime import date, datetime, timedelta, timezone
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from policy_engine import get_eligible_alternatives, _load_customer_row, list_customer_products
from score_customer import score_customer
from nba_priority import rank_alternatives
from dialogue import understand, payment_day

ROOT = Path(__file__).resolve().parents[2]
PRODUCTS = {
    "PERSONAL_LOAN_PAYROLL_DEDUCTION": "Crédito Personal",
    "PERSONAL_LOAN_ACCOUNT_DEBIT": "Crédito Personal",
    "PERSONAL_LOAN_MORTGAGE_BACKED": "Crédito con Garantía Hipotecaria",
    "VEHICLE_LOAN": "Crédito para Vehículo", "HOME_LOAN": "Crédito de Vivienda",
    "STUDY_LOAN": "Crédito de Estudio", "EDUCATION_LOAN": "Crédito de Estudio",
    "CREDICHEQUE": "Credicheque", "OVERDRAFT_ELITE": "Sobregiro Elite",
    "EXTRA_FINANCING": "Extrafinanciamiento", "SALARY_ADVANCE": "Adelanto de Salario",
}
SCENARIOS = [
    ("A1", "Todo al día", "GOLD-G01"), ("A2", "Recordatorio de pago", "GOLD-G03"),
    ("A3", "Mi ingreso llega después", "GOLD-G05"), ("A4", "Pago parcial", "GOLD-G07"),
    ("A5", "Cuidar mi liquidez", "C00252"), ("A6", "Otro canal de contacto", "GOLD-G09"),
    ("A7", "Ayuda paso a paso", "GOLD-G13"), ("A8", "Atención personalizada", "GOLD-G14"),
    ("A9", "Dos créditos activos", "GOLD-G15"),
]
LABELS = {
    "ALT-DATE-SHIFT": ("Usar una nueva fecha", "calendar"),
    "ALT-GRACE-DAYS": ("Revisar días de gracia", "calendar"),
    "ALT-PARTIAL": ("Realizar un pago parcial", "pie"),
    "ALT-AUTOSAVE-PCT": ("Apartar para mi próximo pago", "wallet"),
    "ALT-REMINDER-PAYLINK": ("Pagar mi cuota", "card"),
    "ALT-PAYMENT-PLAN": ("Revisión con un asesor", "headset"),
    "ALT-CHANNEL-SUPPORT": ("Recibir ayuda con el pago", "phone"),
}

def now():
    return datetime.now(timezone.utc).isoformat()

def clean(text):
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")

def spoken_date(value):
    day = date.fromisoformat(value)
    months = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
    return f'{day.day} de {months[day.month - 1]}'

def classify(text):
    t = clean(text)
    if re.search(r'\bno\s+(?:lo\s+)?(?:confirmo|acepto|autorizo)\b', t):
        return 'DECLINE'
    if '?' in t or '¿' in t or re.search(r'\b(que pasa|como funciona)\b', t):
        return 'QUESTION'
    if re.fullmatch(r'(?:si[, ]+)?(?:acepto|confirmo|de acuerdo|estoy de acuerdo|si quiero|me parece bien|usar esta fecha)(?: (?:el pago|la opcion|esta opcion|esa opcion|la operacion))?[.! ]*', t):
        return 'ACCEPT'
    if any(w in t for w in ['no todo', 'solo una parte', 'solamente una parte']):
        return 'LIQUIDITY'
    # Future willingness is not authorization to debit an account now.
    if ((any(w in t for w in ['antes de', 'antes del', 'manana', 'lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo', 'a tiempo']) or re.search(r'\bel \d{1,2}\b', t))
            and re.search(r'\b(puedo|podre|voy a|pagare|pagarlo|pagar el)\b', t)
            and not re.search(r'\bno (?:lo )?(?:puedo|podre|voy|tengo)\b', t)):
        return 'FUTURE_PAY'
    if any(w in t for w in ['enfermedad', 'enferma', 'enfermo', 'hospital', 'emergencia', 'desemple', 'sin empleo']):
        return 'LIQUIDITY'
    checks = [
        ("UNSAFE", ["ignora", "ignore", "system prompt", "sin intereses", "condona", "descuento", "inventa"]),
        ("REFUSAL", ["no me contacten", "no me llamen", "no me escriban", "dejen de", "dejame en paz"]),
        ("ALREADY_PAID", ["ya pague", "ya lo pague", "ya realice el pago"]),
        ("HUMAN", ["asesor", "una persona", "humano", "no reconozco", "reclamo", "fraude"]),
        ("DECLINE", ["no acepto", "no quiero", "no me sirve", "otra opcion"]),
        ("SEEN", ["ya lo veo", "ya veo", "veo el cambio", "ya aparece", "ya se actualizo"]),
        ("TECHNICAL", ["no se usar", "no entiendo la app", "no encuentro", "ayuda con la app", "error", "no me deja"]),
        ("LIQUIDITY", ["no puedo cubrir", "no me alcanza", "parcial", "no tengo dinero", "sin trabajo", "perdi mi", "no puedo pagar"]),
        ("DATE_MISMATCH", ["me pagan", "cobro", "viernes", "quincena", "despues", "otra fecha", "reprogram"]),
        ("PAY", ["pagar ahora", "pagarlo ahora", "pago completo", "quiero pagar", "pagar mi cuota",
                 "puedo cubrir", "puedo pagar", "puedo cubrirlo", "puedo pagarlo", "cubro completo", "cubro toda"]),
        ("FORGOT", ["olvide", "olvido", "recordatorio", "no recordaba"]),
    ]
    for intent, words in checks:
        if any(w in t for w in words):
            return intent
    if t.strip(" .!¡¿?") in {"si", "claro", "ok", "esta bien"}:
        return "ACCEPT"
    # Legacy callers retain deterministic classification. Context is handled by understand().
    return "OTHER"

class DemoError(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status

class BankingService:
    def __init__(self, db_path=None):
        self.db_path = Path(db_path or os.getenv("BA_DEMO_DB", ROOT / ".runtime" / "banking.sqlite3"))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, state TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS demo_profiles (customer_id TEXT PRIMARY KEY, profile TEXT NOT NULL)")
            db.execute('CREATE TABLE IF NOT EXISTS calls (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT, recording TEXT, mime TEXT)')
            if not db.execute('SELECT 1 FROM demo_profiles LIMIT 1').fetchone():
                from risk_engine import load_dataset, load_golden
                import pandas as pd
                all_rows = pd.concat([load_dataset(), load_golden()])
                counts = all_rows.groupby('customer_id').size().to_dict()
                rows = all_rows.drop_duplicates('customer_id')
                demo_names = ['Ana Sofía Martínez', 'Carlos Antonio López', 'María Fernanda Reyes', 'José Daniel Hernández',
                              'Gabriela Alejandra Flores', 'Luis Eduardo Ramírez', 'Valeria Beatriz Rivera', 'Diego Andrés Cruz',
                              'Camila Isabel Torres', 'Roberto Ernesto Gómez', 'Daniela Mercedes Castro', 'Miguel Ángel Santos',
                              'Lucía Patricia Méndez', 'Javier Alexander Aguilar', 'Elena Carolina Vásquez']
                for _, row in rows.iterrows():
                    cid = row['customer_id']
                    name = str(row['full_name_mock'])
                    if cid.startswith('GOLD-'):
                        name = demo_names[int(cid[-2:]) - 1]
                    profile = {'full_name': name, 'document': str(row['dui_mock']),
                               'income_type': str(row['income_type']), 'monthly_income': round(float(row['income_last_30d']), 2),
                               'email': cid.lower() + '@example.test', 'synthetic': True,
                               'credit_count': int(counts[cid])}
                    db.execute('INSERT INTO demo_profiles VALUES (?, ?)', (cid, json.dumps(profile)))

    def random_session(self, multiple=False):
        with self.connect() as db:
            rows = db.execute('SELECT customer_id, profile FROM demo_profiles').fetchall()
        candidates = [cid for cid, raw in rows if not multiple or json.loads(raw)['credit_count'] > 1]
        if not candidates:
            raise DemoError('No hay perfiles con varios créditos disponibles.', 404)
        return self.create(secrets.choice(candidates))

    def start_call(self, sid):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            state = self._read(db, sid)
            old = state.get('active_call_id')
            if old:
                db.execute('UPDATE calls SET ended_at=? WHERE id=? AND ended_at IS NULL', (now(), old))
            call_id = str(uuid4())
            db.execute('INSERT INTO calls(id,session_id,started_at) VALUES (?,?,?)', (call_id, sid, now()))
            state['active_call_id'] = call_id
            state['call_end'] = False
            state['version'] += 1
            state["messages"] = [m for m in state["messages"] if m["role"] == "system"]
            self.assistant(state, f"Hola, {state['name']}. Soy tu asistente de BA A Tiempo. Esta llamada se guarda para que puedas revisarla. ¿Te viene bien conversar sobre tu próximo pago?")
            db.execute('UPDATE sessions SET state=? WHERE id=?', (json.dumps(state), sid))
        return {'call_id': call_id, 'state': self.public(state)}

    def finish_call(self, sid, call_id, path=None, mime=None):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM calls WHERE id=? AND session_id=?', (call_id, sid)).fetchone():
                raise DemoError('No encontramos esta llamada.', 404)
            db.execute('UPDATE calls SET ended_at=COALESCE(ended_at,?), recording=COALESCE(?,recording), mime=COALESCE(?,mime) WHERE id=?',
                       (now(), path, mime, call_id))
            state = self._read(db, sid)
            if state.get('active_call_id') == call_id:
                state['active_call_id'] = None
                state['version'] += 1
                db.execute('UPDATE sessions SET state=? WHERE id=?', (json.dumps(state), sid))
        return self.public(state)

    def conversations(self):
        with self.connect() as db:
            rows = db.execute('SELECT state FROM sessions').fetchall()
            calls = db.execute('SELECT id,session_id,started_at,ended_at,recording FROM calls').fetchall()
        result = []
        for (raw,) in rows:
            s = json.loads(raw)
            if not s['messages']:
                continue
            recordings = [{'id': c[0], 'started_at': c[2], 'ended_at': c[3],
                           'audio_url': f'/api/sessions/{s["id"]}/calls/{c[0]}/audio' if c[4] else None}
                          for c in calls if c[1] == s['id']]
            result.append({'id': s['id'], 'name': s.get('profile', {}).get('full_name', s['name']),
                           'customer_id': s['customer_id'], 'messages': s['messages'], 'events': s['events'],
                           'calls': recordings, 'product': s['product']['name'],
                           'status': 'Acuerdo registrado' if s['receipt'] else 'Revisión con asesor' if s['support'] else 'En conversación',
                           'updated_at': s['messages'][-1]['at']})
        return sorted(result, key=lambda s: s['updated_at'], reverse=True)[:200]

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.db_path, timeout=20)
        try:
            with db:
                yield db
        finally:
            db.close()

    def _build_product(self, customer_id, product_seq):
        """Arma el score + la tarjeta de un crédito puntual. Un cliente puede tener
        más de uno (ver GOLD-G15); cada entrada de state["products"] guarda su
        propio score bajo "_score" (oculto al cliente por public()) para que
        cambiar el foco no tenga que recalcular nada."""
        score = score_customer(customer_id, product_seq)
        if "error" in score:
            return None
        row = _load_customer_row(customer_id, product_seq)
        amount = round(float(row["installment_amount"]), 2)
        due = date.today() + timedelta(days=max(int(score.get("days_to_due") if score.get("days_to_due") is not None else 7), 0))
        return {
            "id": f"{customer_id}:{product_seq}", "product_seq": product_seq,
            "name": PRODUCTS.get(score["profile"]["credit_product"], "Crédito Personal"),
            "number": f"301234567{product_seq}", "code": score["profile"]["credit_product"],
            "installment": amount, "remaining": 0 if score['gates']['current_cycle_paid'] else amount, "due_date": due.isoformat(),
            "original_due_date": due.isoformat(), "outstanding": round(amount * 24, 2),
            "status": "PAID" if score["gates"]["current_cycle_paid"] else "UPCOMING",
            "_score": score,
        }

    def create(self, customer_id="GOLD-G05"):
        products_meta = list_customer_products(customer_id)
        if not products_meta:
            raise DemoError("No encontramos este perfil de demostración.", 404)
        products = [self._build_product(customer_id, p["product_seq"]) for p in products_meta]
        if any(p is None for p in products):
            raise DemoError("No encontramos este perfil de demostración.", 404)
        # El crédito enfocado por defecto es el primero que necesita atención
        # (no pagado); si todos están al día, se enfoca el primero.
        focus = next((p for p in products if p["status"] != "PAID"), products[0])
        score = focus["_score"]
        row = _load_customer_row(customer_id, focus["product_seq"])
        scenario = next((a for a in SCENARIOS if a[2] == customer_id), ("", "Perfil de demostración", customer_id))
        with self.connect() as db:
            profile = json.loads(db.execute('SELECT profile FROM demo_profiles WHERE customer_id=?', (customer_id,)).fetchone()[0])
        state = {
            "id": str(uuid4()), "customer_id": customer_id, "version": 0,
            "name": profile['full_name'].split()[0], "profile": profile, "scenario": scenario[1], "created_at": now(),
            "products": products, "product": focus,
            "accounts": [{"id": "savings", "name": "Cuenta de ahorro", "number": "•• 4821", "balance": round(float(row["current_balance"]), 2)},
                         {"id": "digital", "name": "Cuenta de ahorro", "number": "•• 9034", "balance": 0}],
            "score": score, "barrier": None, "messages": [], "events": [], "offers": [],
            "pending_offer": None, "receipt": None, "support": None, "opt_out": bool(score["gates"]["opt_out_flag"]),
            "reminder": False, "snoozed": False, "channel": score["channel"]["channel_used"],
            "view_hint": None, "call_end": False, "unclear_streak": 0,
        }
        self.refresh_offers(state)
        with self.connect() as db:
            db.execute("INSERT INTO sessions VALUES (?, ?)", (state["id"], json.dumps(state)))
        return self.public(state)

    def select_product(self, state, product_id):
        match = next((p for p in state["products"] if p["id"] == product_id), None)
        if not match:
            raise DemoError("Ese crédito no está disponible en esta sesión.", 409)
        # Reenfoca sobre la MISMA entrada (no una copia nueva) para que cualquier
        # pago/reprogramación previa sobre este crédito se conserve.
        state["product"] = match
        state["score"] = match["_score"]
        state["barrier"] = None
        state["pending_offer"] = None
        state['receipt'] = match.get('_receipt')
        state['support'] = match.get('_support')
        self.refresh_offers(state)

    def _read(self, db, sid):
        record = db.execute("SELECT state FROM sessions WHERE id=?", (sid,)).fetchone()
        if not record:
            raise DemoError("Esta sesión ya no está disponible. Inicia otra demostración.", 404)
        state = json.loads(record[0])
        # Upgrade old single-credit sessions in memory; preserve their balances,
        # history and agreements when the next command persists the state.
        if 'products' not in state:
            state['product'].setdefault('product_seq', 1)
            state['product'].setdefault('id', f"{state['customer_id']}:{state['product']['product_seq']}")
            state['product']['_score'] = state['score']
            state['product']['_receipt'] = state.get('receipt')
            state['product']['_support'] = state.get('support')
            state['products'] = [state['product']]
        if 'profile' not in state:
            row = db.execute('SELECT profile FROM demo_profiles WHERE customer_id=?', (state['customer_id'],)).fetchone()
            if row:
                state['profile'] = json.loads(row[0])
                state['name'] = state['profile']['full_name'].split()[0]
        return state

    def get(self, sid):
        with self.connect() as db:
            return self.public(self._read(db, sid))

    # Emoción no es un dato del modelo -- se infiere de la última barrera
    # detectada por classify() (ya calculada para decidir la respuesta), para
    # que el monitor de admin no duplique una heurística de sentimiento aparte.
    _INTENT_EMOTION = {
        "UNSAFE": "HOSTILE", "REFUSAL": "HOSTILE",
        "LIQUIDITY": "TENSE", "DATE_MISMATCH": "TENSE", "FORGOT": "TENSE",
        "HUMAN": "CONFUSED", "TECHNICAL": "CONFUSED",
        "ACCEPT": "COOPERATIVE", "PAY": "COOPERATIVE", "SEEN": "COOPERATIVE",
    }

    def list_live_calls(self):
        """Conversaciones para el monitor de admin. Se leen directamente de las
        sesiones activas (SQLite) en vez de un log aparte -- una sola fuente de
        verdad para lo que el cliente y el agente realmente dijeron."""
        with self.connect() as db:
            rows = db.execute("SELECT state FROM sessions").fetchall()
        calls = []
        for (raw,) in rows:
            state = json.loads(raw)
            if not state["messages"]:
                continue
            last_intent = next((e["intent"] for e in reversed(state["events"]) if e.get("type") == "BARRIER_CLASSIFIED"), None)
            if state["receipt"] or state["pending_offer"]:
                phase = "CONFIRMING"
            elif state["support"]:
                phase = "ESCALATED"
            elif state["offers"]:
                phase = "OFFERING"
            else:
                phase = "LISTENING"
            calls.append({
                "customer_id": state["customer_id"],
                "history": [{"role": m["role"], "content": m["content"]} for m in state["messages"]],
                "phase": phase,
                "emotion": self._INTENT_EMOTION.get(last_intent, "NEUTRAL"),
                "timestamp": state["messages"][-1]["at"],
            })
        calls.sort(key=lambda c: c["timestamp"])
        return calls

    def public(self, state):
        result = copy.deepcopy(state)
        score = result.pop("score")
        result.get("product", {}).pop("_score", None)
        result.get('product', {}).pop('_receipt', None)
        result.get('product', {}).pop('_support', None)
        for p in result.get("products", []):
            p.pop("_score", None)
            p.pop('_receipt', None)
            p.pop('_support', None)
        result["intervention"] = {
            "show": bool(score["nba"]["should_contact"] and not state["opt_out"] and not state["snoozed"] and state["product"]["status"] == "UPCOMING"),
            "guided": score["profile"]["needs_guided_help"],
            "human": score["profile"]["complex_case"],
            "channel": state["channel"], "scheduled_for": score["nba"]["scheduled_for"],
            "time_window": score["timing"]["best_hour_window"],
        }
        return result

    def refresh_offers(self, state):
        if state["product"]["status"] != "UPCOMING" or state["opt_out"] or state["support"]:
            state["offers"] = []
            return
        risk = {**state["score"]["risk"], **state["score"]["situation"]}
        raw = get_eligible_alternatives(state["customer_id"], risk, state["product"]["product_seq"])
        raw = rank_alternatives(raw, risk["situation_hint"], state["channel"], state["barrier"])
        row = _load_customer_row(state["customer_id"], state["product"]["product_seq"])
        # Policy dates use the synthetic next_due_date (or snapshot fallback).
        reference = row.get("next_due_date")
        if not isinstance(reference, str) or not reference:
            reference = str(row["snapshot_date"])
        anchor = date.fromisoformat(reference[:10])
        eligible = [alt for alt in raw if alt["alt_id"] != "ALT-NONE"
                    and (not state["score"]["profile"]["complex_case"] or alt.get("human_only"))]
        # The catalog rarely has an alt tagged for the exact barrier the customer named
        # (e.g. most non-S2 situations never carry ALT-DATE-SHIFT/ALT-GRACE-DAYS). Prefer
        # a barrier-matched alt when one exists, but never leave the customer with nothing
        # when the Policy Engine already authorized other alternatives for their case.
        barrier_sets = {"DATE_MISMATCH": {"ALT-DATE-SHIFT", "ALT-GRACE-DAYS", "ALT-PAYMENT-PLAN"},
                         "LIQUIDITY": {"ALT-PARTIAL", "ALT-PAYMENT-PLAN", "ALT-AUTOSAVE-PCT"}}
        allowed = barrier_sets.get(state["barrier"])
        if allowed is not None:
            eligible = [alt for alt in eligible if alt["alt_id"] in allowed]
        offers = []
        for alt in eligible:
            alt = dict(alt)
            if alt.get("date"):
                delta = (date.fromisoformat(alt["date"]) - anchor).days
                alt["date"] = (date.fromisoformat(state["product"]["original_due_date"]) + timedelta(days=delta)).isoformat()
            alt["title"], alt["icon"] = LABELS.get(alt["alt_id"], ("Revisar alternativa", "card"))
            offers.append(alt)
        state["offers"] = offers

    def assistant(self, state, text):
        state["messages"].append({"id": str(uuid4()), "role": "assistant", "content": text, "at": now(),
                                  'call_id': state.get('active_call_id'), 'product_id': state['product']['id']})

    def support(self, state):
        if not state["support"]:
            state["support"] = {"id": "BA-" + uuid4().hex[:8].upper(), "status": "Pendiente", "at": now(), "product": state["product"]["name"]}
            state["events"].append({"type": "CALLBACK_REQUESTED", "at": now(), **state["support"]})
            state['product']['_support'] = state['support']
        state["pending_offer"] = None
        state["offers"] = []
        state["view_hint"] = "support"
        self.assistant(state, "Tu solicitud quedó registrada en esta demostración. Un asesor podrá revisar tu caso contigo. No necesitas resolverlo a solas.")

    def select(self, state, offer_id):
        if state["product"]["remaining"] <= 0:
            raise DemoError("Esta cuota ya fue pagada.", 409)
        if offer_id == "PAY_NOW":
            offer = {"alt_id": "PAY_NOW", "title": "Pago de cuota", "amount": state["product"]["remaining"], "type": "PAY_NOW"}
        else:
            self.refresh_offers(state)
            offer = next((o for o in state["offers"] if o["alt_id"] == offer_id), None)
            if not offer:
                raise DemoError("Esta alternativa no está autorizada para tu crédito.", 409)
        if offer.get("human_only") or offer["alt_id"] == "ALT-PAYMENT-PLAN":
            self.support(state)
            return
        if offer["alt_id"] == "ALT-CHANNEL-SUPPORT":
            state["view_hint"] = "guided"
            return
        state["pending_offer"] = {**offer, "token": str(uuid4())}
        self.assistant(state, self.offer_summary(state, offer) + ' El resumen ya está en tu pantalla. ¿Confirmas que registremos esta opción en la demostración?')

    def offer_summary(self, state, offer):
        title = offer['title'] + ' para tu ' + state['product']['name'] + '.'
        if offer.get('date'):
            title += ' La fecha autorizada es el ' + spoken_date(offer['date']) + '.'
        if offer.get('min_amount') or offer.get('amount'):
            title += f" El monto es ${offer.get('min_amount', offer.get('amount')):.2f}."
        if offer['alt_id'] == 'ALT-PARTIAL':
            title += ' El resto de la cuota seguirá pendiente.'
        if offer.get('percentage'):
            title += f" Se apartará el {offer['percentage'] * 100:g}% de tus ingresos."
        return title

    def save_reminder(self, state, pay_date=None):
        due = date.fromisoformat(state['product']['due_date'])
        pay_date = pay_date or due
        if pay_date < date.today() or pay_date > due:
            self.assistant(state, 'Esa fecha está fuera del plazo actual. Podemos revisar una nueva fecha autorizada. ¿Cuándo recibirías tu ingreso?')
            return
        when = max(date.today(), pay_date - timedelta(days=1)).isoformat()
        reminder = {'id': 'BA-' + uuid4().hex[:8].upper(), 'at': now(), 'type': 'REMINDER_SAVED',
                    'title': 'Recordatorio programado', 'date': when, 'payment_date': pay_date.isoformat(),
                    'channel': state['channel'],
                    'product_id': state['product']['id'], 'status': 'Programado en la demo'}
        state['reminder'] = True
        state['scheduled_reminder'] = reminder
        state['pending_offer'] = None
        state['offers'] = []
        state['events'].append(reminder)
        channel = 'llamada' if reminder['channel'] == 'CALL' else 'mensaje'
        self.assistant(state, f"Qué bueno que puedes pagarlo dentro del plazo. Dejé programado el recordatorio por {channel} para el {spoken_date(when)}, "
                       + ('un día antes de tu pago. ' if pay_date > date.today() else 'hoy, porque tu pago es hoy. ')
                       + 'Puedes verificarlo en el historial. En esta demostración queda registrado; no se envían mensajes ni llamadas externas. ¿Ya lo ves?')

    def confirm(self, state, token):
        offer = state["pending_offer"]
        if not offer or offer["token"] != token:
            raise DemoError("La confirmación ya no es válida. Revisa de nuevo la opción.", 409)
        if offer["alt_id"] != "PAY_NOW":
            self.refresh_offers(state)
            valid = next((o for o in state["offers"] if o["alt_id"] == offer["alt_id"]), None)
            if not valid or any(offer.get(k) != valid.get(k) for k in ("date", "min_amount", "percentage", "min_percentage")):
                raise DemoError("Las condiciones cambiaron. Revisa las opciones actualizadas.", 409)
        product = state["product"]
        paid = None
        if offer["alt_id"] in {"PAY_NOW", "ALT-REMINDER-PAYLINK", "ALT-PARTIAL"}:
            paid = min(product["remaining"], offer.get("min_amount", product["remaining"]))
            if state["accounts"][0]["balance"] < paid:
                raise DemoError("El saldo de esta cuenta no alcanza. Puedes revisar alternativas o solicitar ayuda.", 409)
            state["accounts"][0]["balance"] = round(state["accounts"][0]["balance"] - paid, 2)
            product["remaining"] = round(product["remaining"] - paid, 2)
            product["outstanding"] = max(0, round(product["outstanding"] - paid, 2))
            product["status"] = "PAID" if product["remaining"] == 0 else "PARTIAL"
        elif offer.get("date"):
            product["due_date"] = offer["date"]
            product["status"] = "RESCHEDULED"
        elif offer["alt_id"] == "ALT-AUTOSAVE-PCT":
            state["autosave"] = offer["percentage"]
            product["status"] = "SAVING"
        receipt = {"id": "BA-" + uuid4().hex[:8].upper(), "at": now(), "title": offer["title"],
                   "alt_id": offer["alt_id"], "amount": paid, "date": offer.get("date"),
                   "percentage": offer.get("percentage"), "status": "Registrado", "product": product["name"]}
        state["receipt"] = receipt
        state['product']['_receipt'] = receipt
        state["events"].append({"type": "AGREEMENT_CONFIRMED", **receipt})
        state["pending_offer"] = None
        state["view_hint"] = "receipt"
        self.refresh_offers(state)
        self.assistant(state, "Listo, tu operación simulada quedó registrada y tu producto ya está actualizado. ¿Ya puedes ver el cambio en tu pantalla?")

    def message(self, state, text, decision=None):
        state["messages"].append({"id": str(uuid4()), "role": "user", "content": text, "at": now(),
                                  'call_id': state.get('active_call_id'), 'product_id': state['product']['id']})
        decision = decision or {'intent': classify(text), 'opening': '', 'provider': 'rules'}
        intent = decision['intent']
        state['conversation_engine'] = decision['provider']
        state['events'].append({'type': 'MODEL_RESPONSE', 'at': now(), **{k: v for k, v in decision.items() if k != 'opening'}})
        state["events"].append({"type": "BARRIER_CLASSIFIED", "intent": intent, "at": now()})
        if intent != "OTHER":
            state["unclear_streak"] = 0
        if intent == 'FUTURE_PAY' or (state.get('awaiting_payment_day') and payment_day(text, state['product']['due_date'])):
            day = payment_day(text, state['product']['due_date'])
            state['awaiting_payment_day'] = day is None
            if day:
                self.save_reminder(state, day)
            else:
                self.assistant(state, 'Me alegra que puedas pagarlo dentro del plazo. ¿Qué día planeas hacerlo? Así dejamos el recordatorio para el día anterior.')
        elif intent == 'SWITCH_PRODUCT' and decision.get('product_id'):
            self.select_product(state, decision['product_id'])
            self.assistant(state, 'Claro, ahora estamos revisando tu ' + state['product']['name'] + '. ¿Qué necesitas resolver con este pago?')
        elif intent == 'SELECT_OPTION' and decision.get('option_id'):
            self.select(state, decision['option_id'])
        elif intent == "UNSAFE":
            state["pending_offer"] = None
            self.assistant(state, "Entiendo que buscas una solución. Solo puedo mostrarte condiciones autorizadas para tu crédito. Podemos revisar las opciones disponibles o solicitar un asesor.")
        elif intent == "REFUSAL":
            state["opt_out"] = True
            state["pending_offer"] = None
            self.refresh_offers(state)
            state["call_end"] = True
            self.assistant(state, "Entendido. Registré que no deseas recibir recordatorios en esta demostración. Puedes volver a pedir ayuda cuando lo necesites. Que tengas un buen día.")
        elif intent == "ALREADY_PAID":
            state["snoozed"] = True
            state["pending_offer"] = None
            self.assistant(state, "Gracias por avisarme. Registré tu aviso de pago y pausé el recordatorio. El estado del crédito solo cambiará al verificar el pago; si lo necesitas, podemos solicitar una revisión.")
        elif intent == "HUMAN":
            self.support(state)
        elif intent == "TECHNICAL":
            state["view_hint"] = "guided"
            self.assistant(state, "Claro, vamos paso a paso. Toca Mis Productos, selecciona tu crédito y busca Próximo pago. No necesito tu contraseña ni códigos. También puedes pedir ayuda a una persona.")
        elif intent == "SEEN" and (state["receipt"] or state.get('scheduled_reminder') or state['support']):
            state["call_end"] = True
            self.assistant(state, "Perfecto, gracias por confirmarlo. Tu comprobante está disponible en el historial. Gracias por tu tiempo; que tengas un excelente día.")
        elif intent == "DECLINE":
            state["pending_offer"] = None
            self.assistant(state, "Está bien, no he registrado ningún acuerdo. Podemos revisar otra alternativa o conversar con un asesor.")
        elif intent == "PAY":
            self.select(state, "PAY_NOW")
        elif intent == "ACCEPT":
            if state["pending_offer"]:
                try:
                    self.confirm(state, state["pending_offer"]["token"])
                except DemoError as exc:
                    if 'saldo' not in exc.message.lower():
                        raise
                    state['pending_offer'] = None
                    self.assistant(state, 'El saldo disponible no alcanza para este pago; no se hizo ningún cargo. Podemos buscar otra opción o solicitar que un asesor revise tu caso. ¿Qué prefieres?')
            elif state["receipt"]:
                self.assistant(state, "Tu operación ya quedó registrada. Cuando veas el cambio en pantalla, dime «ya lo veo».")
            elif state["offers"] and state["barrier"]:
                self.select(state, state["offers"][0]["alt_id"])
            else:
                self.assistant(state, 'Gracias por darme este momento. Cuéntame, ¿podrás cubrir tu próximo pago dentro del plazo o hay algo que te lo esté dificultando?')
        elif intent in {"DATE_MISMATCH", "LIQUIDITY", "FORGOT"}:
            state["pending_offer"] = None
            state["barrier"] = intent
            self.refresh_offers(state)
            if state["score"]["profile"]["complex_case"]:
                state["view_hint"] = "support"
                self.assistant(state, "Gracias por contármelo. Tu caso necesita una revisión personalizada. Puedo ayudarte a solicitar una llamada con un asesor.")
            elif state["offers"]:
                opening = decision.get('opening') or ('Lamento que estés pasando por este momento. Gracias por confiarme lo que sucede.' if intent == 'LIQUIDITY' else 'Gracias por contármelo. Busquemos algo que se ajuste a tu situación.')
                self.assistant(state, opening + ' Podemos revisar: ' + self.offer_summary(state, state['offers'][0]) + ' ¿Te parece que revisemos esta opción?')
            else:
                self.assistant(state, "Gracias por explicármelo. No hay una alternativa automática autorizada que responda a esta situación. Podemos solicitar una revisión con un asesor.")
        elif intent == 'BUSY':
            self.assistant(state, 'Claro, respeto tu tiempo. Podemos continuar cuando te venga bien. Tu conversación queda guardada aquí. Que tengas un buen día.')
            state['call_end'] = True
        elif intent == 'QUESTION' and state['pending_offer']:
            self.assistant(state, self.offer_summary(state, state['pending_offer']) + ' Todavía no hemos hecho cambios. Puedes confirmarla o decirme qué te gustaría aclarar.')
        elif intent == 'GREETING' or re.search(r'\b(hola|buenas|buenos dias)\b', clean(text)):
            self.assistant(state, f"Hola, {state['name']}. Soy tu asistente de BA A Tiempo. Gracias por conversar conmigo. ¿Te viene bien que revisemos juntos tu próximo pago?")
        else:
            self.assistant(state, decision.get('opening') or 'Te escucho con gusto. ¿Qué es lo que más te dificulta hacer este pago? Busquemos una opción que puedas cumplir con tranquilidad.')

    def command(self, sid, command):
        decision = None
        if command['action'] == 'message':
            with self.connect() as db:
                snapshot = self._read(db, sid)
            if command.get('version') != snapshot['version']:
                raise DemoError('La sesión cambió. Actualizamos tu pantalla; vuelve a intentarlo.', 409)
            # Network inference stays OUTSIDE the SQLite write lock.
            decision = understand(snapshot, command['text'], classify(command['text']))
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            state = self._read(db, sid)
            # A stale tab cannot confirm an old agreement or repeat a payment.
            if command.get("version") != state["version"]:
                raise DemoError("La sesión cambió. Actualizamos tu pantalla; vuelve a intentarlo.", 409)
            state["view_hint"] = None
            state["call_end"] = False
            action = command["action"]
            if action == "message":
                self.message(state, command["text"], decision)
            elif action == 'greet':
                self.assistant(state, f"Hola, {state['name']}. Soy tu asistente de BA A Tiempo. Estoy aquí para escucharte y ayudarte con tu {state['product']['name']}. ¿Te viene bien que conversemos un momento?")
            elif action == "select":
                self.select(state, command["offer_id"])
            elif action == "confirm":
                self.confirm(state, command["token"])
            elif action == "cancel":
                state["pending_offer"] = None
            elif action == "callback":
                self.support(state)
            elif action == "seen":
                if not state["receipt"]:
                    raise DemoError("No hay una operación que confirmar.")
                state["call_end"] = True
                self.assistant(state, "Gracias por confirmarlo. Tu comprobante está en el historial. Que tengas un excelente día.")
            elif action == "snooze":
                state["snoozed"] = True
            elif action == "reminder":
                self.save_reminder(state)
            elif action == "channel":
                state["channel"] = command["channel"]
                state["events"].append({"type": "CHANNEL_CHANGED", "at": now(), "channel": state["channel"], "title": "Preferencia de contacto actualizada"})
            elif action == "select_product":
                self.select_product(state, command["product_id"])
            elif action == "clear_chat":
                state["messages"] = [m for m in state["messages"] if m["role"] == "system"]
            else:
                raise DemoError("Acción no reconocida.")
            # state["product"] is the live, mutable focus; state["products"] is a
            # separate JSON-persisted copy (SQLite round-trips through json.dumps/
            # loads, so Python object aliasing between the two does not survive
            # across commands). Re-sync explicitly so a payment/reschedule on the
            # focused credit is reflected the next time the products list is read.
            for i, p in enumerate(state.get("products", [])):
                if p.get("id") == state["product"].get("id"):
                    state["products"][i] = state["product"]
                    break
            state["version"] += 1
            db.execute("UPDATE sessions SET state=? WHERE id=?", (json.dumps(state), sid))
        return self.public(state)
