from __future__ import annotations
import math
from typing import Mapping
from ..models import DomainDefinition, WorldState


def pressure_from_margin(value: float, threshold: float) -> float:
    """PROTOTYPE-ONLY monotone pressure mapping, not asserted canonical Φ mathematics."""
    if value <= threshold:
        return 1.0
    margin = value - threshold
    return 1.0 / (1.0 + margin)


def collapse_horizon(value: float, threshold: float, baseline_drift: float) -> float:
    """Time-to-threshold under constant baseline drift. inf if not approaching threshold."""
    if value <= threshold:
        return 0.0
    if baseline_drift >= 0:
        return math.inf
    return max(0.0, (value - threshold) / (-baseline_drift))


def governing_from_horizon(horizon: float, domain: DomainDefinition) -> bool:
    """Prototype gate. A domain-specific governing_horizon must be registered."""
    if domain.governing_horizon is None:
        return False
    return horizon <= domain.governing_horizon


def dependency_close(governing: set[str], domains: Mapping[str, DomainDefinition]) -> set[str]:
    out = set(governing)
    changed = True
    while changed:
        changed = False
        for did in list(out):
            for dep in domains[did].dependencies:
                if dep not in out:
                    out.add(dep)
                    changed = True
    return out


def regime_label(governing_domains: set[str], horizons: Mapping[str, float]) -> str:
    """Prototype diagnostic label only; not a canonical ℛ implementation."""
    if not governing_domains:
        return "PROTOTYPE_STEADY"
    if any(horizons[d] <= 0 for d in governing_domains):
        return "PROTOTYPE_THRESHOLD_BREACH"
    return "PROTOTYPE_GOVERNING_PRESSURE"
