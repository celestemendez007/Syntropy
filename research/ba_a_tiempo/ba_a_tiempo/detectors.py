"""Detectores custom, en módulo propio para que joblib los pueda deserializar
desde cualquier script (si quedaran definidos dentro de un módulo ejecutado
como __main__, joblib no podría recargarlos después)."""
from sklearn.covariance import MinCovDet
from . import config as C


class ZScoreDetector:
    """Baseline simple: distancia de Mahalanobis robusta (MinCovDet) como score de anomalía.
    Interpretación: qué tan lejos está el vector de features del centro robusto de la población,
    en unidades de covarianza. Es el modelo más simple y más explicable de los cuatro."""

    def __init__(self):
        self.mcd = MinCovDet(support_fraction=0.85, random_state=C.SEED)

    def fit(self, X):
        self.mcd.fit(X)
        return self

    def score_samples(self, X):
        d = self.mcd.mahalanobis(X)
        return -d
