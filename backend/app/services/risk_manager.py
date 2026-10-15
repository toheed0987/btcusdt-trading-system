"""
Risk manager: applies Admin Panel-configured guardrails before any position
is opened or closed. Used by both the live paper-trading loop and the
backtester so behavior is consistent between simulation and "live".
"""
from dataclasses import dataclass


@dataclass
class RiskDecision:
    allowed: bool
    reason: str = ""
    quantity: float = 0.0
    stop_loss: float = None
    take_profit: float = None


def size_position(capital: float, price: float, position_size_pct: float) -> float:
    notional = capital * position_size_pct
    return round(notional / price, 8)


def compute_stop_take(entry_price: float, side: str, stop_loss_pct: float, take_profit_pct: float):
    if side == "LONG":
        stop_loss = entry_price * (1 - stop_loss_pct)
        take_profit = entry_price * (1 + take_profit_pct)
    else:  # SHORT
        stop_loss = entry_price * (1 + stop_loss_pct)
        take_profit = entry_price * (1 - take_profit_pct)
    return round(stop_loss, 8), round(take_profit, 8)


def evaluate_new_position(
    trading_enabled: bool,
    open_position_count: int,
    max_open_positions: int,
    capital: float,
    price: float,
    side: str,
    position_size_pct: float,
    stop_loss_pct: float,
    take_profit_pct: float,
    daily_realized_pnl_pct: float,
    daily_loss_limit_pct: float,
) -> RiskDecision:
    """Central gate: every rule that must pass before opening a position."""
    if not trading_enabled:
        return RiskDecision(allowed=False, reason="Trading is disabled in Admin Panel.")

    if open_position_count >= max_open_positions:
        return RiskDecision(allowed=False, reason="Max open positions reached.")

    if daily_realized_pnl_pct <= -abs(daily_loss_limit_pct):
        return RiskDecision(allowed=False, reason="Daily loss limit reached; trading paused for today.")

    qty = size_position(capital, price, position_size_pct)
    if qty <= 0:
        return RiskDecision(allowed=False, reason="Computed position size is zero.")

    stop_loss, take_profit = compute_stop_take(price, side, stop_loss_pct, take_profit_pct)
    return RiskDecision(allowed=True, quantity=qty, stop_loss=stop_loss, take_profit=take_profit)


def should_close_position(current_price: float, side: str, stop_loss: float, take_profit: float):
    """Returns a close reason string, or None if the position should stay open."""
    if side == "LONG":
        if stop_loss and current_price <= stop_loss:
            return "stop_loss"
        if take_profit and current_price >= take_profit:
            return "take_profit"
    else:
        if stop_loss and current_price >= stop_loss:
            return "stop_loss"
        if take_profit and current_price <= take_profit:
            return "take_profit"
    return None
