"""
Market scanner: scans a list of symbols in parallel and returns ranked
trade setups. The Finora-AI-style feed showing top opportunities across
many assets at once.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List
from apps.market.services import get_market_service
from apps.market.providers.base import ProviderError, DataNotFoundError
from apps.market.indicators import add_indicators
from .scalper import detect_scalp
from .forecast import expected_move_over_horizon
from .insights import generate_insight

logger = logging.getLogger(__name__)


def _scan_one(symbol: str, interval: str, period: str) -> dict:
    """Fetch data, compute indicators, generate signal for one symbol."""
    try:
        svc = get_market_service()
        df = svc.get_candles(symbol, interval, period)
        df_ind = add_indicators(df)
        sig = detect_scalp(df_ind, symbol.upper())
        em = expected_move_over_horizon(df_ind, horizon_bars=10, interval=interval)
        insight = generate_insight(sig, em)
        return {
            "ok": True,
            "symbol": symbol.upper(),
            "price": sig.indicators.get("price"),
            "direction": sig.direction,
            "action": sig.action,
            "strength": sig.strength,
            "confidence": sig.confidence,
            "entry": sig.entry,
            "stop_loss": sig.stop_loss,
            "take_profit": sig.take_profit,
            "risk_reward": sig.risk_reward,
            "risk_pct": sig.risk_pct,
            "reward_pct": sig.reward_pct,
            "regime": (sig.regime or {}).get("regime", ""),
            "htf_trend": sig.htf_trend,
            "patterns_bullish": (sig.patterns or {}).get("bullish", []),
            "patterns_bearish": (sig.patterns or {}).get("bearish", []),
            "expected_move_pct": em.get("expected_move_pct") if em.get("ok") else None,
            "fits_target": em.get("fits_2_5_pct_target") if em.get("ok") else False,
            "insight": insight,
            "top_reasons": sig.reasons[:4],
            "rsi": sig.indicators.get("rsi"),
            "volume_ratio": sig.indicators.get("volume_ratio"),
        }
    except (DataNotFoundError, ProviderError) as e:
        return {"ok": False, "symbol": symbol.upper(), "error": str(e)}
    except Exception as e:
        logger.warning("Scanner error for %s: %s", symbol, e)
        return {"ok": False, "symbol": symbol.upper(), "error": str(e)}


def scan_symbols(symbols: List[str], interval: str = "1h", period: str = "1mo",
                 min_confidence: float = 40, max_workers: int = 8) -> dict:
    """
    Scan many symbols in parallel, return ranked list of trade opportunities.

    Returns dict with:
      - signals: list of signal dicts sorted by confidence desc
      - scanned: total symbols scanned
      - actionable: count with action=TRADE
      - failed: list of symbols that failed to fetch
    """
    results = []
    failed = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_scan_one, s, interval, period): s for s in symbols}
        for fut in as_completed(futures):
            sym = futures[fut]
            try:
                r = fut.result(timeout=30)
                if r.get("ok"):
                    results.append(r)
                else:
                    failed.append({"symbol": sym, "error": r.get("error", "unknown")})
            except Exception as e:
                failed.append({"symbol": sym, "error": str(e)})

    # Filter and sort
    signals = [r for r in results if r["direction"] != "NEUTRAL"
               and r["confidence"] >= min_confidence]
    # Sort: actionable first, then by confidence desc, then by fits-target bonus
    def sort_key(r):
        action_rank = {"TRADE": 0, "WATCH": 1, "WAIT": 2}.get(r["action"], 3)
        target_bonus = -5 if r.get("fits_target") else 0
        return (action_rank, -r["confidence"] + target_bonus, -r["risk_reward"])
    signals.sort(key=sort_key)

    neutral = [r for r in results if r["direction"] == "NEUTRAL"]

    return {
        "ok": True,
        "scanned": len(symbols),
        "returned": len(results),
        "signals": signals,
        "neutral": neutral,
        "failed": failed,
        "actionable": sum(1 for s in signals if s["action"] == "TRADE"),
        "interval": interval,
        "period": period,
    }
