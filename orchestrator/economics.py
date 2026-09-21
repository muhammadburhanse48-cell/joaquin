"""Derived targets from Doc 06. Pure arithmetic; every number is shown to the seats."""

from __future__ import annotations

META_FEE = 0.01
GOOGLE_FEE = 0.10
NET_MARGIN_TARGET = 0.20  # m
SPEND_FLOOR_MULTIPLE = 1.5
FALLBACK_FLOOR = 30.0


def breakeven_roas(v: float, f: float = META_FEE) -> float:
    return (1 + f) / (1 - v)


def target_roas(v: float, f: float = META_FEE, m: float = NET_MARGIN_TARGET) -> float:
    return (1 + f) / (1 - v - m)


def max_cpa(aov: float, v: float, f: float = META_FEE, m: float = NET_MARGIN_TARGET) -> float:
    return aov * (1 - v - m) / (1 + f)


def net_margin(roas: float, v: float, f: float = META_FEE) -> float:
    return 1 - v - (1 + f) / roas


def cap_two_roas(aov: float, v: float | None = None) -> float:
    """The cap targets a 2 ROAS: AOV/2, bound by the 20%-net max CPA when that is tighter."""
    cap = aov / 2
    return min(cap, max_cpa(aov, v)) if v is not None else cap


def spend_floor(target_cpa: float | None) -> float:
    """>=1.5x target CPA per creative; $30 fallback when there is no target CPA."""
    return SPEND_FLOOR_MULTIPLE * target_cpa if target_cpa else FALLBACK_FLOOR


def variable_cost_ratio(cogs_pct: float, payment_fee_pct: float, shipping_pct: float) -> float:
    return (cogs_pct + payment_fee_pct + shipping_pct) / 100


def derived_targets_text(economics: dict | None, target_cpa: float | None) -> str:
    """Human-readable derived targets, with the arithmetic. Never invents an input."""
    floor = spend_floor(target_cpa)
    lines = [f"spend floor per creative = {'1.5 x target CPA' if target_cpa else 'fallback'} = ${floor:.2f}"]
    need = ("aov", "cogs_pct", "payment_fee_pct", "shipping_pct")
    if not economics or any(economics.get(k) is None for k in need):
        lines.append("economics: inputs needed (AOV, COGS %, payment fee %, uncovered shipping %) "
                     "— NO net-margin verdict may be issued")
        if economics and economics.get("aov"):
            lines.append(f"2-ROAS cap = AOV/2 = {economics['aov']}/2 = ${economics['aov'] / 2:.2f}")
        return "\n".join(lines)
    aov = float(economics["aov"])
    v = variable_cost_ratio(*(float(economics[k]) for k in need[1:]))
    f = META_FEE
    lines += [
        f"v (variable cost ratio) = ({economics['cogs_pct']}+{economics['payment_fee_pct']}"
        f"+{economics['shipping_pct']})/100 = {v:.4f}; f (Meta fee) = {f}; m = {NET_MARGIN_TARGET}",
        f"breakeven ROAS = (1+f)/(1-v) = {breakeven_roas(v, f):.2f}",
        f"target ROAS (20% net) = (1+f)/(1-v-m) = {target_roas(v, f):.2f}",
        f"max CPA = AOV(1-v-m)/(1+f) = {max_cpa(aov, v, f):.2f}",
        f"2-ROAS cap = min(AOV/2, max CPA) = {cap_two_roas(aov, v):.2f}",
    ]
    if economics.get("provisional"):
        lines.append("PROVISIONAL: economics were modelled, not measured")
    return "\n".join(lines)
