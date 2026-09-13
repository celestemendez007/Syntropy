"""Batch predictions from deployed artifacts, distinct from frozen benchmarks."""
import json
import time
from functools import lru_cache
from pathlib import Path
import numpy as np
import pandas as pd
import risk_engine as risk

ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def predictions():
    started = time.perf_counter()
    data = risk.load_dataset()
    def transformed(features, logs):
        x = data[features].astype(float).copy()
        for col in logs:
            x[col] = np.log1p(np.clip(x[col], 0, None))
        return x
    lr, scaler = risk._load_risk_model_and_scaler()
    x = transformed(risk.LR_FEATURES, risk.LR_LOG1P)
    probability = lr.predict_proba(pd.DataFrame(scaler.transform(x), columns=x.columns))[:, 1]
    model, scaler = risk._load_model_and_scaler()
    x = transformed(risk.IF_FEATURES, risk.IF_LOG1P)
    anomaly = np.clip((-model.score_samples(pd.DataFrame(scaler.transform(x), columns=x.columns)) + .2) / .8, 0, 1)
    blend = risk.RISK_W_LR * probability + risk.RISK_W_IF * anomaly
    records = []
    for pos, (_, row) in enumerate(data.iterrows()):
        records.append({'customer_id': row.customer_id, 'name': row.full_name_mock,
                        'product': row.credit_product, 'installment': round(float(row.installment_amount), 2),
                        'probability': round(float(probability[pos]), 4), 'risk_score': round(float(blend[pos]), 4),
                        'risk_level': 'HIGH' if blend[pos] >= .65 else 'MEDIUM' if blend[pos] >= .35 else 'LOW',
                        'synthetic_label': int(row.synthetic_late_payment_next_cycle)})
    records.sort(key=lambda r: r['probability'], reverse=True)
    return {'summary': {'customers': int(data.customer_id.nunique()), 'credits': len(data),
                        'predicted_late': int((probability >= .5).sum()), 'threshold': .5,
                        'expected_late': round(float(probability.sum()), 1),
                        'synthetic_late': int(data.synthetic_late_payment_next_cycle.sum()),
                        'high_risk': int((blend >= .65).sum()),
                        'at_risk_installments': round(float(data.loc[probability >= .5, 'installment_amount'].sum()), 2),
                        'inference_ms': round((time.perf_counter() - started) * 1000),
                        'snapshot': str(data.snapshot_date.iloc[0])},
            'distribution': {level: sum(r['risk_level'] == level for r in records) for level in ['LOW', 'MEDIUM', 'HIGH']},
            'rows': records}


def benchmarks():
    base = ROOT / 'research' / 'ba_a_tiempo' / 'outputs'
    return {name: json.loads((base / (name + '_benchmark.json')).read_text(encoding='utf-8'))
            for name in ['risk', 'anomaly', 'channel_timing', 'score_customer']}
