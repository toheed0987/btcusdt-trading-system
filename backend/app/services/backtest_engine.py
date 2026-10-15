"""
Vectorized-ish event-driven backtester. Walks through historical candles,
generates model probabilities candle-by-candle (no lookahead: model only
ever sees data up to and including the current candle), applies the same
signal engine and risk manager used in live trading, and produces:
  - equity curve
  - trade log
  - monthly returns
  - performance metrics (Sharpe, profit factor, max drawdown, win rate)
"""
import math
from datetime import datetime
from typing import List, Dict, Any

import numpy as np
import pandas as pd

from app.ml.features import FEATURE_COLUMNS, build_features
from app.ml.signal_engine import generate_signal
from app.services.risk_manager import compute_stop_take, should_close_position, size_position


def run_backtest(
    ohlcv_df: pd.DataFrame,
    model,
    initial_capital: float = 10000,
    buy_prob_threshold: float = 0.60,
    sell_prob_threshold: float = 0.60,
    min_confidence: float = 0.15,
    stop_loss_pct: float = 0.02,
    take_profit_pct: float = 0.04,
    position_size_pct: float = 0.10,
    warmup: int = 60,
) -> Dict[str, Any]:
    feats = build_features(ohlcv_df).fillna(0)

    capital = initial_capital
    equity_curve: List[Dict[str, Any]] = []
    trades: List[Dict[str, Any]] = []
    open_pos = None  # dict: side, entry_price, qty, stop_loss, take_profit, entry_time

    for i in range(warmup, len(feats)):
        row = feats.iloc[i]
        price = float(row["close"])
        ts = row["open_time"]

        X = feats.iloc[[i]][FEATURE_COLUMNS]
        prob_up = float(model.predict_proba(X)[:, 1][0])

        # --- manage existing position first (stop loss / take profit / flip) ---
        if open_pos is not None:
            reason = should_close_position(price, open_pos["side"], open_pos["stop_loss"],
                                            open_pos["take_profit"])
            sig = generate_signal(prob_up, buy_prob_threshold, sell_prob_threshold, min_confidence)
            flip = (open_pos["side"] == "LONG" and sig.action == "SELL") or \
                   (open_pos["side"] == "SHORT" and sig.action == "BUY")
            if reason or flip:
                exit_reason = reason or "signal_flip"
                pnl = (price - open_pos["entry_price"]) * open_pos["qty"] if open_pos["side"] == "LONG" \
                    else (open_pos["entry_price"] - price) * open_pos["qty"]
                pnl_pct = pnl / (open_pos["entry_price"] * open_pos["qty"]) if open_pos["qty"] else 0
                capital += pnl
                trades.append({
                    "entry_time": open_pos["entry_time"], "exit_time": ts,
                    "side": open_pos["side"], "entry_price": open_pos["entry_price"],
                    "exit_price": price, "quantity": open_pos["qty"],
                    "pnl": round(pnl, 2), "pnl_pct": round(pnl_pct * 100, 4),
                    "exit_reason": exit_reason,
                })
                open_pos = None
        else:
            sig = generate_signal(prob_up, buy_prob_threshold, sell_prob_threshold, min_confidence)

        # --- consider opening a new position ---
        if open_pos is None and sig.action in ("BUY", "SELL"):
            side = "LONG" if sig.action == "BUY" else "SHORT"
            qty = size_position(capital, price, position_size_pct)
            stop_loss, take_profit = compute_stop_take(price, side, stop_loss_pct, take_profit_pct)
            if qty > 0:
                open_pos = {
                    "side": side, "entry_price": price, "qty": qty,
                    "stop_loss": stop_loss, "take_profit": take_profit, "entry_time": ts,
                }

        # mark-to-market equity for the curve
        unrealized = 0.0
        if open_pos is not None:
            unrealized = (price - open_pos["entry_price"]) * open_pos["qty"] if open_pos["side"] == "LONG" \
                else (open_pos["entry_price"] - price) * open_pos["qty"]
        equity_curve.append({"t": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                              "equity": round(capital + unrealized, 2)})

    metrics = compute_metrics(equity_curve, trades, initial_capital)
    monthly_returns = compute_monthly_returns(equity_curve)

    return {
        "equity_curve": equity_curve,
        "trades": trades,
        "monthly_returns": monthly_returns,
        "metrics": metrics,
    }


def compute_metrics(equity_curve: List[Dict], trades: List[Dict], initial_capital: float) -> Dict[str, Any]:
    if not equity_curve:
        return {}

    equities = np.array([p["equity"] for p in equity_curve], dtype=float)
    returns = np.diff(equities) / np.where(equities[:-1] == 0, 1, equities[:-1])

    # Sharpe ratio (annualized, assuming 1-minute bars -> ~525600 bars/year)
    periods_per_year = 525600
    if returns.std() > 0:
        sharpe = float(np.mean(returns) / np.std(returns) * math.sqrt(periods_per_year))
    else:
        sharpe = 0.0

    # Max drawdown
    running_max = np.maximum.accumulate(equities)
    drawdowns = (equities - running_max) / np.where(running_max == 0, 1, running_max)
    max_drawdown = float(drawdowns.min()) if len(drawdowns) else 0.0

    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    win_rate = len(wins) / len(trades) if trades else 0.0

    gross_profit = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)

    final_equity = equities[-1]
    total_return_pct = (final_equity - initial_capital) / initial_capital * 100

    return {
        "total_return_pct": round(total_return_pct, 3),
        "sharpe_ratio": round(sharpe, 3),
        "max_drawdown_pct": round(max_drawdown * 100, 3),
        "win_rate": round(win_rate, 4),
        "profit_factor": None if profit_factor == float("inf") else round(profit_factor, 3),
        "total_trades": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "final_equity": round(float(final_equity), 2),
    }


def compute_monthly_returns(equity_curve: List[Dict]) -> List[Dict[str, Any]]:
    if not equity_curve:
        return []
    df = pd.DataFrame(equity_curve)
    df["t"] = pd.to_datetime(df["t"])
    df = df.set_index("t")
    monthly = df["equity"].resample("ME").last()
    monthly_ret = monthly.pct_change().fillna(monthly.iloc[0] / equity_curve[0]["equity"] - 1 if len(monthly) else 0)
    return [{"month": idx.strftime("%Y-%m"), "return_pct": round(float(val) * 100, 3)}
            for idx, val in monthly_ret.items()]
