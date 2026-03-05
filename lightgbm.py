"""Local compatibility shim for environments without the real lightgbm package."""

from sklearn.ensemble import GradientBoostingClassifier


class LGBMClassifier:
    def __init__(self, n_estimators=100, learning_rate=0.1, random_state=None, **kwargs):
        self._model = GradientBoostingClassifier(
            n_estimators=n_estimators,
            learning_rate=learning_rate,
            random_state=random_state,
        )
        self.feature_importances_ = None

    def fit(self, X, y):
        self._model.fit(X, y)
        self.feature_importances_ = getattr(self._model, "feature_importances_", None)
        return self

    def score(self, X, y):
        return self._model.score(X, y)

    def predict_proba(self, X):
        return self._model.predict_proba(X)
