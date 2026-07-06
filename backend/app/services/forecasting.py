"""Forecasting: ridge-regularised linear trend + weekly seasonality on real history.

Uses scikit-learn when available; falls back to a pure-numpy least-squares fit
so the demo never breaks on a missing wheel.
"""

from datetime import date, timedelta

import numpy as np

try:
    from sklearn.linear_model import Ridge

    def _fit_predict(X: np.ndarray, y: np.ndarray, X_future: np.ndarray) -> np.ndarray:
        model = Ridge(alpha=1.0)
        model.fit(X, y)
        return model.predict(X_future)

except ImportError:  # pragma: no cover

    def _fit_predict(X: np.ndarray, y: np.ndarray, X_future: np.ndarray) -> np.ndarray:
        Xb = np.hstack([X, np.ones((len(X), 1))])
        coef, *_ = np.linalg.lstsq(Xb, y, rcond=None)
        return np.hstack([X_future, np.ones((len(X_future), 1))]) @ coef


def _features(days: np.ndarray, weekdays: np.ndarray) -> np.ndarray:
    """Design matrix: linear trend + one-hot weekday seasonality."""
    onehot = np.zeros((len(days), 7))
    onehot[np.arange(len(days)), weekdays] = 1
    return np.hstack([days.reshape(-1, 1) / 365.0, onehot])


def forecast_series(history: list[tuple[date, float]], horizon: int = 30) -> dict:
    """history: list of (day, value) sorted ascending. Returns forecast + confidence band."""
    if len(history) < 14:
        return {"forecast": [], "confidence": 0.0}

    dates = [h[0] for h in history]
    values = np.array([h[1] for h in history], dtype=float)
    day_idx = np.array([(d - dates[0]).days for d in dates], dtype=float)
    weekdays = np.array([d.weekday() for d in dates])

    X = _features(day_idx, weekdays)
    preds_in = _fit_predict(X, values, X)
    resid_std = float(np.std(values - preds_in))

    future_dates = [dates[-1] + timedelta(days=i + 1) for i in range(horizon)]
    fut_idx = np.array([(d - dates[0]).days for d in future_dates], dtype=float)
    fut_wd = np.array([d.weekday() for d in future_dates])
    preds = _fit_predict(X, values, _features(fut_idx, fut_wd))
    preds = np.maximum(preds, 0)

    # R² as a rough confidence proxy
    ss_res = float(np.sum((values - preds_in) ** 2))
    ss_tot = float(np.sum((values - values.mean()) ** 2)) or 1.0
    r2 = max(0.0, 1 - ss_res / ss_tot)

    return {
        "forecast": [
            {
                "day": d.isoformat(),
                "value": round(float(p), 0),
                "low": round(max(float(p) - 1.28 * resid_std, 0), 0),
                "high": round(float(p) + 1.28 * resid_std, 0),
            }
            for d, p in zip(future_dates, preds)
        ],
        "confidence": round(r2 * 100, 1),
        # slope of the fitted line itself: first vs last forecast week (full weekday mix each)
        "trend_pct_per_month": round(
            float(np.mean(preds[-7:]) - np.mean(preds[:7])) / max(float(np.mean(values[-30:])), 1.0)
            / max(horizon - 7, 1) * 30 * 100, 1
        ),
    }


def restock_predictions(products: list) -> list[dict]:
    """Days-until-stockout per product from stock level and daily demand."""
    out = []
    for p in products:
        demand = max(p.daily_demand, 0.1)
        days_left = p.stock / demand
        out.append(
            {
                "product_id": p.id,
                "name": p.name,
                "stock": p.stock,
                "daily_demand": round(demand, 1),
                "days_until_stockout": round(days_left, 1),
                "restock_by": (date.today() + timedelta(days=max(int(days_left) - 3, 0))).isoformat(),
                "suggested_order": max(int(demand * 30) - p.stock, 0),
                "status": "critical" if days_left < 5 else "low" if days_left < 12 else "healthy",
            }
        )
    out.sort(key=lambda r: r["days_until_stockout"])
    return out
