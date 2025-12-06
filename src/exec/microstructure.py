from __future__ import annotations

from typing import Dict


def spread_bps(bid: float, ask: float) -> float:
    mid = (bid + ask) / 2
    return (ask - bid) / mid * 10_000 if mid else 0.0


def impact_linear(notional: float, adv: float, coefficient: float = 0.5) -> float:
    if adv <= 0:
        return 0.0
    participation = notional / adv
    return coefficient * participation * 100  # bps per % ADV


def depth_score(volume: float, adv: float) -> float:
    return volume / adv if adv else 0.0

