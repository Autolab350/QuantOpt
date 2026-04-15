from dataclasses import dataclass, field
from greeks_calculator import (
    black_scholes_price,
    calculate_leg_greeks,
    aggregate_greeks,
)
import numpy as np


@dataclass
class OptionLeg:
    option_type: str  # "call" or "put"
    side: str  # "long" or "short"
    strike: float
    quantity: int = 1

    def premium(self, S, T, r, sigma):
        return black_scholes_price(self.option_type, S, self.strike, T, r, sigma)

    def payoff_at_expiry(self, S_range):
        sign = 1.0 if self.side == "long" else -1.0
        if self.option_type == "call":
            intrinsic = np.maximum(S_range - self.strike, 0)
        else:
            intrinsic = np.maximum(self.strike - S_range, 0)
        return sign * intrinsic * self.quantity

    def greeks(self, S, T, r, sigma):
        return calculate_leg_greeks(
            self.option_type, self.side, S, self.strike, T, r, sigma, self.quantity
        )


@dataclass
class Strategy:
    name: str
    legs: list
    greek_profile: dict
    category: str  # "credit", "debit", "neutral", "directional"
    description: str = ""
    explanation: str = ""

    def net_premium(self, S, T, r, sigma):
        total = 0.0
        for leg in self.legs:
            prem = leg.premium(S, T, r, sigma)
            if leg.side == "short":
                total += prem
            else:
                total -= prem
        return total

    def payoff_at_expiry(self, S_range, S, T, r, sigma):
        net_prem = self.net_premium(S, T, r, sigma)
        total_payoff = np.zeros_like(S_range, dtype=float)
        for leg in self.legs:
            total_payoff += leg.payoff_at_expiry(S_range)
        return total_payoff + net_prem

    def greeks(self, S, T, r, sigma):
        all_greeks = [leg.greeks(S, T, r, sigma) for leg in self.legs]
        return aggregate_greeks(all_greeks)

    def get_explanation(self, S, T, r, sigma):
        g = self.greeks(S, T, r, sigma)
        parts = [self.explanation]
        if g["theta"] > 0:
            parts.append(
                f"Theta is {g['theta']:.4f} per day. Time decay works in your favor."
            )
        else:
            parts.append(
                f"Theta is {g['theta']:.4f} per day. Time decay works against you."
            )
        if abs(g["delta"]) < 0.10:
            parts.append("Delta is near zero. This trade is direction-neutral.")
        elif g["delta"] > 0:
            parts.append(
                f"Delta is {g['delta']:.4f}. This trade profits when price rises."
            )
        else:
            parts.append(
                f"Delta is {g['delta']:.4f}. This trade profits when price falls."
            )
        if g["vega"] < 0:
            parts.append(
                "Vega is negative. A spike in implied volatility will hurt this position."
            )
        else:
            parts.append(
                "Vega is positive. Rising implied volatility helps this position."
            )
        if abs(g.get("vanna", 0)) > 0.01:
            parts.append(
                f"Vanna is {g['vanna']:.4f}. Your Delta will shift if volatility changes."
            )
        return " ".join(parts)


GREEK_TOOLTIPS = {
    "delta": "Delta measures how much the option price changes for a $1 move in the stock. A Delta of 0.50 means the option gains $0.50 if the stock rises $1.",
    "gamma": "Gamma measures how fast Delta changes. High Gamma means your risk profile shifts quickly as the stock moves.",
    "theta": "Theta is time decay. Positive Theta means you earn money each day. Negative Theta means you lose money each day just by holding.",
    "vega": "Vega measures sensitivity to volatility. Positive Vega profits from rising IV. Negative Vega profits from falling IV.",
    "rho": "Rho measures sensitivity to interest rate changes. Usually small for short-dated options.",
    "vanna": "Vanna is a second-order Greek. It shows how your Delta changes when volatility moves. Important for earnings plays.",
    "vomma": "Vomma shows how your Vega accelerates. If Vomma is high a small IV change causes a large shift in Vega exposure.",
    "charm": "Charm shows how Delta decays over time. Useful for knowing how to adjust positions over weekends.",
}


def build_strategy(name, S, K, T, r, sigma, spread_width=None):
    if spread_width is None:
        spread_width = round(S * 0.02, 0)
        if spread_width < 1:
            spread_width = 1.0

    w = spread_width
    half_w = round(spread_width / 2, 0)
    if half_w < 1:
        half_w = 1.0

    strategies = {
        "Long Call": Strategy(
            name="Long Call",
            legs=[OptionLeg("call", "long", K)],
            greek_profile={
                "Delta": "positive",
                "Gamma": "positive",
                "Vega": "positive",
                "Theta": "negative",
                "Rho": "positive",
            },
            category="debit",
            description="Buy a call option. Profits when price rises above strike plus premium paid.",
            explanation="You are buying the right to purchase shares at the strike price. Your risk is limited to the premium paid.",
        ),
        "Long Put": Strategy(
            name="Long Put",
            legs=[OptionLeg("put", "long", K)],
            greek_profile={
                "Delta": "negative",
                "Gamma": "positive",
                "Vega": "positive",
                "Theta": "negative",
                "Rho": "negative",
            },
            category="debit",
            description="Buy a put option. Profits when price falls below strike minus premium paid.",
            explanation="You are buying the right to sell shares at the strike price. Your risk is limited to the premium paid.",
        ),
        "Short Call": Strategy(
            name="Short Call",
            legs=[OptionLeg("call", "short", K)],
            greek_profile={
                "Delta": "negative",
                "Gamma": "negative",
                "Vega": "negative",
                "Theta": "positive",
                "Rho": "negative",
            },
            category="credit",
            description="Sell a call option. Collects premium. Profits when price stays below strike.",
            explanation="You are selling the obligation to deliver shares. You collect premium upfront but face unlimited risk if price rises.",
        ),
        "Short Put": Strategy(
            name="Short Put",
            legs=[OptionLeg("put", "short", K)],
            greek_profile={
                "Delta": "positive",
                "Gamma": "negative",
                "Vega": "negative",
                "Theta": "positive",
                "Rho": "positive",
            },
            category="credit",
            description="Sell a put option. Collects premium. Profits when price stays above strike.",
            explanation="You are selling the obligation to buy shares. You collect premium but must buy the stock if it drops below the strike.",
        ),
        "Bull Call Spread": Strategy(
            name="Bull Call Spread",
            legs=[
                OptionLeg("call", "long", K),
                OptionLeg("call", "short", K + w),
            ],
            greek_profile={
                "Delta": "positive",
                "Gamma": "positive",
                "Vega": "positive",
                "Theta": "negative",
                "Rho": "positive",
            },
            category="debit",
            description="Buy a lower strike call and sell a higher strike call. Profits from moderate upward moves.",
            explanation="This is a debit spread. You pay upfront. Max profit is the width of the strikes minus what you paid. Max loss is limited to the debit.",
        ),
        "Bear Put Spread": Strategy(
            name="Bear Put Spread",
            legs=[
                OptionLeg("put", "long", K),
                OptionLeg("put", "short", K - w),
            ],
            greek_profile={
                "Delta": "negative",
                "Gamma": "positive",
                "Vega": "positive",
                "Theta": "negative",
                "Rho": "negative",
            },
            category="debit",
            description="Buy a higher strike put and sell a lower strike put. Profits from moderate downward moves.",
            explanation="This is a debit spread. You pay upfront. Max profit is the width of the strikes minus what you paid. Max loss is limited to the debit.",
        ),
        "Bull Put Spread": Strategy(
            name="Bull Put Spread",
            legs=[
                OptionLeg("put", "short", K),
                OptionLeg("put", "long", K - w),
            ],
            greek_profile={
                "Delta": "positive",
                "Gamma": "negative",
                "Vega": "negative",
                "Theta": "positive",
                "Rho": "positive",
            },
            category="credit",
            description="Sell a higher strike put and buy a lower strike put. Collects premium. Profits when price stays above the sold strike.",
            explanation="This is a credit spread. You collect cash upfront. Max loss is capped at the width of the strikes minus the credit received. Capital efficient.",
        ),
        "Bear Call Spread": Strategy(
            name="Bear Call Spread",
            legs=[
                OptionLeg("call", "short", K),
                OptionLeg("call", "long", K + w),
            ],
            greek_profile={
                "Delta": "negative",
                "Gamma": "negative",
                "Vega": "negative",
                "Theta": "positive",
                "Rho": "negative",
            },
            category="credit",
            description="Sell a lower strike call and buy a higher strike call. Collects premium. Profits when price stays below the sold strike.",
            explanation="This is a credit spread. You collect cash upfront. Max loss is capped at the width of the strikes minus the credit received.",
        ),
        "Long Straddle": Strategy(
            name="Long Straddle",
            legs=[
                OptionLeg("call", "long", K),
                OptionLeg("put", "long", K),
            ],
            greek_profile={
                "Delta": "neutral",
                "Gamma": "positive",
                "Vega": "positive",
                "Theta": "negative",
                "Rho": "neutral",
            },
            category="debit",
            description="Buy both a call and a put at the same strike. Profits from large moves in either direction.",
            explanation="You are betting on a big move but you do not know the direction. You need the stock to move far enough to cover both premiums.",
        ),
        "Short Straddle": Strategy(
            name="Short Straddle",
            legs=[
                OptionLeg("call", "short", K),
                OptionLeg("put", "short", K),
            ],
            greek_profile={
                "Delta": "neutral",
                "Gamma": "negative",
                "Vega": "negative",
                "Theta": "positive",
                "Rho": "neutral",
            },
            category="credit",
            description="Sell both a call and a put at the same strike. Collects maximum premium. Profits when price stays near the strike.",
            explanation="You are betting the stock stays flat. You collect heavy premium but face large risk if the stock moves significantly in either direction.",
        ),
        "Long Strangle": Strategy(
            name="Long Strangle",
            legs=[
                OptionLeg("call", "long", K + half_w),
                OptionLeg("put", "long", K - half_w),
            ],
            greek_profile={
                "Delta": "neutral",
                "Gamma": "positive",
                "Vega": "positive",
                "Theta": "negative",
                "Rho": "neutral",
            },
            category="debit",
            description="Buy an out-of-the-money call and an out-of-the-money put. Cheaper than a straddle but needs a bigger move.",
            explanation="Similar to a straddle but cheaper because the strikes are further from the current price. The stock needs to move more for you to profit.",
        ),
        "Short Strangle": Strategy(
            name="Short Strangle",
            legs=[
                OptionLeg("call", "short", K + half_w),
                OptionLeg("put", "short", K - half_w),
            ],
            greek_profile={
                "Delta": "neutral",
                "Gamma": "negative",
                "Vega": "negative",
                "Theta": "positive",
                "Rho": "neutral",
            },
            category="credit",
            description="Sell an out-of-the-money call and an out-of-the-money put. Wider profit zone than a short straddle.",
            explanation="You collect premium from both sides. The stock can move within a range and you still profit. Risk is large if the stock breaks out of that range.",
        ),
        "Iron Condor": Strategy(
            name="Iron Condor",
            legs=[
                OptionLeg("put", "long", K - w),
                OptionLeg("put", "short", K - half_w),
                OptionLeg("call", "short", K + half_w),
                OptionLeg("call", "long", K + w),
            ],
            greek_profile={
                "Delta": "neutral",
                "Gamma": "negative",
                "Vega": "negative",
                "Theta": "positive",
                "Rho": "neutral",
            },
            category="credit",
            description="A combination of a Bull Put Spread and a Bear Call Spread. Four legs. Premium collected. Defined risk on both sides.",
            explanation="This is the capital-efficient premium collection strategy. You define a price range. If the stock stays inside that range you keep the credit. Risk is capped on both sides.",
        ),
        "Iron Butterfly": Strategy(
            name="Iron Butterfly",
            legs=[
                OptionLeg("put", "long", K - w),
                OptionLeg("put", "short", K),
                OptionLeg("call", "short", K),
                OptionLeg("call", "long", K + w),
            ],
            greek_profile={
                "Delta": "neutral",
                "Gamma": "negative",
                "Vega": "negative",
                "Theta": "positive",
                "Rho": "neutral",
            },
            category="credit",
            description="Sell a straddle and buy wings for protection. Higher premium than Iron Condor but narrower profit zone.",
            explanation="Collects more premium than an Iron Condor because the short strikes are at the money. But the stock must stay very close to the strike for max profit.",
        ),
        "Long Butterfly": Strategy(
            name="Long Butterfly",
            legs=[
                OptionLeg("call", "long", K - half_w),
                OptionLeg("call", "short", K, quantity=2),
                OptionLeg("call", "long", K + half_w),
            ],
            greek_profile={
                "Delta": "neutral",
                "Gamma": "positive",
                "Vega": "negative",
                "Theta": "positive",
                "Rho": "neutral",
            },
            category="debit",
            description="Buy one lower call, sell two middle calls, buy one higher call. Cheap bet that the stock lands near the middle strike.",
            explanation="Low cost trade with a high reward if the stock pins near the center strike at expiration. Max loss is the small debit paid.",
        ),
        "Collar": Strategy(
            name="Collar",
            legs=[
                OptionLeg("put", "long", K - half_w),
                OptionLeg("call", "short", K + half_w),
            ],
            greek_profile={
                "Delta": "neutral",
                "Gamma": "neutral",
                "Vega": "neutral",
                "Theta": "neutral",
                "Rho": "neutral",
            },
            category="neutral",
            description="Used with existing stock. Buy a protective put and sell a covered call. Locks in a price range.",
            explanation="Protects your downside with a put while giving up upside through the sold call. The call premium offsets the put cost. Often near zero cost.",
        ),
        "Calendar Spread": Strategy(
            name="Calendar Spread",
            legs=[
                OptionLeg("call", "short", K),
                OptionLeg("call", "long", K),
            ],
            greek_profile={
                "Delta": "neutral",
                "Gamma": "low",
                "Vega": "positive",
                "Theta": "positive",
                "Rho": "neutral",
            },
            category="debit",
            description="Sell a near-term option and buy a longer-term option at the same strike. Profits from time decay differential.",
            explanation="The short-term option decays faster than the long-term one. You profit from this difference. Works best when the stock stays near the strike.",
        ),
    }

    if name in strategies:
        return strategies[name]
    return strategies


def get_all_strategies(S, K, T, r, sigma, spread_width=None):
    return build_strategy(None, S, K, T, r, sigma, spread_width)


def suggest_strategies(prefs, S, K, T, r, sigma, spread_width=None):
    all_strats = get_all_strategies(S, K, T, r, sigma, spread_width)
    matches = []
    for name, strat in all_strats.items():
        score = 0
        total = 0
        for greek, desired in prefs.items():
            if desired == "any":
                continue
            total += 1
            actual = strat.greek_profile.get(greek, "neutral")
            if actual == desired:
                score += 1
            elif desired == "neutral" and actual in ("neutral", "low"):
                score += 1
        match_score = score / total if total > 0 else 0.0
        matches.append((match_score, name, strat))
    matches.sort(key=lambda x: x[0], reverse=True)
    return matches[:5]
