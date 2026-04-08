"""
Bidirectional LSTM price predictor.

Uses a curated feature set (OHLCV + key indicators) and separate scalers
for features and target. Supports multi-step recursive forecasting and
computes proper out-of-sample metrics.

NOTE: TensorFlow is an optional dependency. If not installed, the predictor
gracefully disables itself. The rest of the app (scalp signals, scanner,
forecast, etc.) works without it.
"""
import logging
import numpy as np
import pandas as pd

try:
    import tensorflow  # noqa: F401
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_error, r2_score

logger = logging.getLogger(__name__)


FEATURE_COLS = [
    "Open", "High", "Low", "Close", "Volume",
    "RSI_14", "MACD", "MACD_Signal", "MACD_Hist",
    "BB_Upper", "BB_Lower", "BB_PercentB",
    "EMA_9", "EMA_21", "SMA_50",
    "ATR_14", "ADX_14", "Stoch_K", "Stoch_D",
    "OBV", "VWAP", "MFI_14", "Vol_Ratio", "Returns",
]

TARGET_COL = "Close"


class LSTMPredictor:
    """Encapsulates feature scaling, model training, and forecasting."""

    def __init__(self, lookback: int = 60, bidirectional: bool = True,
                 dropout: float = 0.2, lstm_units=(64, 32)):
        self.lookback = lookback
        self.bidirectional = bidirectional
        self.dropout = dropout
        self.lstm_units = lstm_units
        self.feat_scaler = None
        self.tgt_scaler = None
        self.model = None
        self.history = None
        self.close_idx = FEATURE_COLS.index(TARGET_COL)

    # ------------------------------------------------------------------
    def _build_sequences(self, features: np.ndarray, targets: np.ndarray):
        X, y = [], []
        for i in range(self.lookback, len(features)):
            X.append(features[i - self.lookback:i])
            y.append(targets[i])
        return np.asarray(X, dtype=np.float32), np.asarray(y, dtype=np.float32)

    def prepare(self, df: pd.DataFrame, test_frac: float = 0.2):
        """Split → fit scalers on train only → sequence."""
        missing = [c for c in FEATURE_COLS if c not in df.columns]
        if missing:
            raise ValueError(f"Missing feature columns: {missing}")
        df = df[FEATURE_COLS].dropna().copy()
        if len(df) < self.lookback + 50:
            raise ValueError(f"Need at least {self.lookback + 50} rows, got {len(df)}")

        split = int(len(df) * (1 - test_frac))
        self.feat_scaler = MinMaxScaler((0, 1))
        self.tgt_scaler = MinMaxScaler((0, 1))
        self.feat_scaler.fit(df.iloc[:split].values)
        self.tgt_scaler.fit(df.iloc[:split][[TARGET_COL]].values)

        features_s = self.feat_scaler.transform(df.values)
        targets_s = self.tgt_scaler.transform(df[[TARGET_COL]].values).flatten()

        X, y = self._build_sequences(features_s, targets_s)
        # Align split after sequence creation
        train_end = split - self.lookback
        X_train, X_test = X[:train_end], X[train_end:]
        y_train, y_test = y[:train_end], y[train_end:]
        self._last_sequence = features_s[-self.lookback:]
        self._full_df = df
        return X_train, y_train, X_test, y_test, split

    # ------------------------------------------------------------------
    def build(self, input_shape):
        if not TF_AVAILABLE:
            raise RuntimeError("TensorFlow not installed. Install with: pip install tensorflow")
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import LSTM, Dense, Dropout, Bidirectional, Input
        from tensorflow.keras.optimizers import Adam
        u1, u2 = self.lstm_units
        m = Sequential()
        m.add(Input(shape=input_shape))
        if self.bidirectional:
            m.add(Bidirectional(LSTM(u1, return_sequences=True)))
            m.add(Dropout(self.dropout))
            m.add(Bidirectional(LSTM(u2)))
        else:
            m.add(LSTM(u1, return_sequences=True))
            m.add(Dropout(self.dropout))
            m.add(LSTM(u2))
        m.add(Dropout(self.dropout))
        m.add(Dense(16, activation="relu"))
        m.add(Dense(1))
        m.compile(optimizer=Adam(learning_rate=0.001), loss="mse", metrics=["mae"])
        self.model = m
        return m

    def fit(self, X_train, y_train, X_val, y_val, epochs=50, batch_size=32, callbacks=None):
        from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
        cbs = [
            EarlyStopping(monitor="val_loss", patience=10, restore_best_weights=True),
            ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=5, min_lr=1e-5),
        ]
        if callbacks:
            cbs.extend(callbacks)
        self.history = self.model.fit(
            X_train, y_train, validation_data=(X_val, y_val),
            epochs=epochs, batch_size=batch_size, callbacks=cbs, verbose=0,
        )
        return self.history

    # ------------------------------------------------------------------
    def predict(self, X) -> np.ndarray:
        preds_s = self.model.predict(X, verbose=0).flatten()
        return self.tgt_scaler.inverse_transform(preds_s.reshape(-1, 1)).flatten()

    def forecast(self, steps: int = 5) -> list:
        """Recursive multi-step forecast."""
        if self._last_sequence is None:
            raise RuntimeError("prepare() must be called first")
        seq = self._last_sequence.copy()
        forecasts = []
        for _ in range(steps):
            x = seq.reshape(1, seq.shape[0], seq.shape[1])
            pred_s = float(self.model.predict(x, verbose=0).flatten()[0])
            pred = float(self.tgt_scaler.inverse_transform([[pred_s]])[0, 0])
            forecasts.append(pred)
            new_row = seq[-1].copy()
            new_row[self.close_idx] = pred_s
            seq = np.vstack([seq[1:], new_row])
        return forecasts

    # ------------------------------------------------------------------
    @staticmethod
    def evaluate(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
        y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
        mae = float(mean_absolute_error(y_true, y_pred))
        denom = np.where(y_true == 0, np.nan, y_true)
        mape = float(np.nanmean(np.abs((y_true - y_pred) / denom)) * 100)
        rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
        r2 = float(r2_score(y_true, y_pred))
        if len(y_true) > 1:
            da = float(np.mean(np.sign(np.diff(y_true)) == np.sign(np.diff(y_pred))) * 100)
        else:
            da = 0.0
        return {"MAE": mae, "MAPE": mape, "RMSE": rmse, "R2": r2, "DirectionalAccuracy": da}
