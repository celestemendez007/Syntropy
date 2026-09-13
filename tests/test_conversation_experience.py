"""Consent, real predictions, demo identities and persisted call boundaries."""
import io
import json
import sys
from datetime import date, timedelta
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src' / 'backend'))
from app_service import BankingService, classify
from main import app
from dialogue import payment_day


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('BA_DEMO_DB', str(tmp_path / 'sessions.sqlite3'))
    monkeypatch.setenv('BA_DIALOGUE_MODE', 'rules')
    with TestClient(app) as c:
        yield c


def command(c, s, text):
    r = c.post(f'/api/sessions/{s["id"]}/commands', json={'action': 'message', 'version': s['version'], 'text': text})
    assert r.status_code == 200, r.text
    return r.json()


def test_random_login_uses_database_identity_and_multiple_credits(client):
    s = client.post('/api/demo/login', json={'multiple': True}).json()
    assert len(s['products']) > 1
    assert s['profile']['credit_count'] == len(s['products'])
    assert s['name'] == s['profile']['full_name'].split()[0]
    assert s['profile']['synthetic'] and s['profile']['email'].endswith('@example.test')
    assert next(p for p in s['products'] if p['status'] == 'PAID')['remaining'] == 0


@pytest.mark.parametrize('text', ['Puedo pagar antes de la fecha', 'Voy a pagar mañana', 'Puedo pagarlo el martes'])
def test_future_payment_is_not_a_debit(client, text):
    s = client.post('/api/sessions', json={}).json()
    initial = s['accounts']
    s = command(client, s, text)
    assert s['pending_offer'] is None and s['receipt'] is None and s['accounts'] == initial
    assert s['scheduled_reminder']['date'] < s['scheduled_reminder']['payment_date']
    assert s['scheduled_reminder']['product_id'] == s['product']['id']
    s = command(client, s, 'Ya lo veo')
    assert s['call_end']


@pytest.mark.parametrize('text', ['No confirmo', '¿Qué pasa si confirmo?', 'Confirmo que no puedo pagar', 'Estoy de acuerdo con mi hermano'])
def test_ambiguous_and_negative_language_never_confirms_payment(client, text):
    s = client.post('/api/sessions', json={'customer_id': 'GOLD-G03'}).json()
    s = client.post(f'/api/sessions/{s["id"]}/commands', json={'action': 'select', 'offer_id': 'PAY_NOW', 'version': s['version']}).json()
    initial = s['accounts']
    s = command(client, s, text)
    assert s['receipt'] is None and s['accounts'] == initial


def test_conversation_confirm_executes_and_can_be_verified(client):
    s = client.post('/api/sessions', json={}).json()
    original = s['product']['due_date']
    s = command(client, s, 'Me pagan después')
    s = command(client, s, 'Acepto')
    assert s['pending_offer'] and s['product']['due_date'] == original
    s = command(client, s, 'Confirmo')
    assert s['receipt'] and s['product']['due_date'] != original
    s = command(client, s, 'Ya veo el cambio')
    assert s['call_end']


def test_emergency_understanding_and_no_irrelevant_pay_now_offer(client):
    s = client.post('/api/sessions', json={'customer_id': 'GOLD-G07'}).json()
    s = command(client, s, 'Mi mamá está enferma y gasté en sus medicinas')
    assert s['barrier'] == 'LIQUIDITY'
    assert not any(o['alt_id'] == 'ALT-REMINDER-PAYLINK' for o in s['offers'])
    assert not s['receipt']


def test_call_transcript_lifecycle_and_recording_scope(client):
    s = client.post('/api/sessions', json={}).json()
    other = client.post('/api/sessions', json={}).json()
    started = client.post(f'/api/sessions/{s["id"]}/calls').json()
    cid = started['call_id']; s = started['state']
    assert s['messages'][-1]['call_id'] == cid
    s = command(client, s, 'Hola')
    assert s['messages'][-1]['call_id'] == cid
    assert client.post(f'/api/sessions/{other["id"]}/calls/{cid}/end').status_code == 404
    assert client.put(f'/api/sessions/{s["id"]}/calls/{cid}/audio', content=b'not audio', headers={'content-type': 'audio/webm'}).status_code == 400
    response = client.post(f'/api/sessions/{s["id"]}/calls/{cid}/end')
    assert response.json()['active_call_id'] is None
    record = next(c for c in client.get('/api/admin/conversations').json() if c['id'] == s['id'])
    assert record['calls'][0]['ended_at'] and record['calls'][0]['audio_url'] is None


def test_admin_predictions_match_the_deployed_model(client):
    from risk_engine import _risk_prob_lr, load_dataset
    result = client.get('/api/admin/overview').json()
    assert result['summary']['customers'] == 3000
    assert sum(result['distribution'].values()) == result['summary']['credits']
    records = client.get('/api/admin/predictions?q=C00001').json()
    row = next(r for r in records['rows'] if r['customer_id'] == 'C00001')
    actual = _risk_prob_lr(load_dataset().query('customer_id == "C00001"').iloc[0])
    assert abs(row['probability'] - actual) < .0001
    assert result['benchmarks']['risk']['LogisticRegression']['auc'] == .7369


def test_no_model_call_inside_write_lock(client, monkeypatch):
    import app_service
    s = client.post('/api/sessions', json={}).json()
    def inference(state, text, fallback):
        with app.state.service.connect() as db:
            db.execute('BEGIN IMMEDIATE')
        return {'intent': 'OTHER', 'opening': 'Gracias por contármelo. ¿Qué te ayudaría con tu pago?', 'provider': 'test'}
    monkeypatch.setattr(app_service, 'understand', inference)
    assert command(client, s, 'Necesito orientación')['conversation_engine'] == 'test'


def test_legacy_session_migration_preserves_existing_payment(client):
    service = app.state.service
    s = service.create()
    with service.connect() as db:
        state = service._read(db, s['id'])
        state.pop('products'); state.pop('profile')
        state['product']['remaining'] = 27.5
        db.execute('UPDATE sessions SET state=? WHERE id=?', (json.dumps(state), s['id']))
    migrated = service.get(s['id'])
    assert migrated['products'][0]['remaining'] == 27.5
    assert migrated['profile']['full_name'] and migrated['product']['remaining'] == 27.5
