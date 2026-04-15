import numpy as np


def calculate_payoff_curve(strategy, S, T, r, sigma, num_points=500):
    price_min = S * 0.7
    price_max = S * 1.3
    S_range = np.linspace(price_min, price_max, num_points)
    payoffs = strategy.payoff_at_expiry(S_range, S, T, r, sigma)
    return S_range, payoffs


def calculate_max_profit(strategy, S, T, r, sigma):
    S_range, payoffs = calculate_payoff_curve(strategy, S, T, r, sigma)
    return float(np.max(payoffs))


def calculate_max_loss(strategy, S, T, r, sigma):
    S_range, payoffs = calculate_payoff_curve(strategy, S, T, r, sigma)
    return float(np.min(payoffs))


def calculate_breakeven_points(strategy, S, T, r, sigma):
    S_range, payoffs = calculate_payoff_curve(strategy, S, T, r, sigma, num_points=2000)
    breakevens = []
    for i in range(len(payoffs) - 1):
        if payoffs[i] * payoffs[i + 1] < 0:
            ratio = abs(payoffs[i]) / (abs(payoffs[i]) + abs(payoffs[i + 1]))
            be = S_range[i] + ratio * (S_range[i + 1] - S_range[i])
            breakevens.append(round(float(be), 2))
    return breakevens


def calculate_profit_area(strategy, S, T, r, sigma):
    S_range, payoffs = calculate_payoff_curve(strategy, S, T, r, sigma, num_points=2000)
    profitable_count = np.sum(payoffs > 0)
    total_count = len(payoffs)
    if total_count == 0:
        return 0.0
    return round(float(profitable_count / total_count) * 100.0, 2)


def calculate_capital_requirement(strategy, S, T, r, sigma):
    net_prem = strategy.net_premium(S, T, r, sigma)

    if strategy.category == "credit":
        strikes = sorted([leg.strike for leg in strategy.legs])
        if len(strikes) >= 2:
            max_width = strikes[-1] - strikes[0]
        else:
            max_width = S * 0.20
        capital = (max_width - abs(net_prem)) * 100
        return round(max(capital, 0.0), 2)

    elif strategy.category == "debit":
        capital = abs(net_prem) * 100
        return round(capital, 2)

    else:
        capital = S * 100 * 0.20
        return round(capital, 2)


def calculate_risk_reward_ratio(strategy, S, T, r, sigma):
    max_profit = calculate_max_profit(strategy, S, T, r, sigma)
    max_loss = calculate_max_loss(strategy, S, T, r, sigma)
    if max_profit <= 0:
        return float("inf")
    return round(abs(max_loss) / max_profit, 2)


def full_risk_report(strategy, S, T, r, sigma):
    max_profit = calculate_max_profit(strategy, S, T, r, sigma)
    max_loss = calculate_max_loss(strategy, S, T, r, sigma)
    breakevens = calculate_breakeven_points(strategy, S, T, r, sigma)
    profit_area = calculate_profit_area(strategy, S, T, r, sigma)
    capital_req = calculate_capital_requirement(strategy, S, T, r, sigma)
    risk_reward = calculate_risk_reward_ratio(strategy, S, T, r, sigma)
    net_premium = strategy.net_premium(S, T, r, sigma)
    greeks = strategy.greeks(S, T, r, sigma)

    return {
        "strategy_name": strategy.name,
        "category": strategy.category,
        "net_premium": round(net_premium, 2),
        "max_profit": round(max_profit, 2),
        "max_loss": round(max_loss, 2),
        "breakeven_points": breakevens,
        "profit_area_pct": profit_area,
        "capital_required": capital_req,
        "risk_reward_ratio": risk_reward,
        "greeks": {k: round(v, 6) for k, v in greeks.items()},
        "legs": [
            {
                "type": leg.option_type,
                "side": leg.side,
                "strike": leg.strike,
                "quantity": leg.quantity,
            }
            for leg in strategy.legs
        ],
    }
