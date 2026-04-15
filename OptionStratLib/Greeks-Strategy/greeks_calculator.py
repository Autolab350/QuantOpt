import numpy as np
from scipy.stats import norm


def _validate_inputs(S, K, T, r, sigma):
    if S <= 0:
        raise ValueError("Underlying price must be positive")
    if K <= 0:
        raise ValueError("Strike price must be positive")
    if T <= 0:
        raise ValueError("Time to expiration must be positive")
    if sigma <= 0 or sigma > 5.0:
        raise ValueError("Implied volatility must be between 0 and 5.0")


def _d1(S, K, T, r, sigma):
    return (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))


def _d2(S, K, T, r, sigma):
    return _d1(S, K, T, r, sigma) - sigma * np.sqrt(T)


def black_scholes_price(option_type, S, K, T, r, sigma):
    _validate_inputs(S, K, T, r, sigma)
    d1 = _d1(S, K, T, r, sigma)
    d2 = _d2(S, K, T, r, sigma)
    if option_type == "call":
        return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    elif option_type == "put":
        return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    else:
        raise ValueError(f"Unknown option type: {option_type}")


def delta(option_type, S, K, T, r, sigma):
    _validate_inputs(S, K, T, r, sigma)
    d1 = _d1(S, K, T, r, sigma)
    if option_type == "call":
        return norm.cdf(d1)
    else:
        return norm.cdf(d1) - 1.0


def gamma(S, K, T, r, sigma):
    _validate_inputs(S, K, T, r, sigma)
    d1 = _d1(S, K, T, r, sigma)
    return norm.pdf(d1) / (S * sigma * np.sqrt(T))


def theta(option_type, S, K, T, r, sigma):
    _validate_inputs(S, K, T, r, sigma)
    d1 = _d1(S, K, T, r, sigma)
    d2 = _d2(S, K, T, r, sigma)
    term1 = -(S * norm.pdf(d1) * sigma) / (2.0 * np.sqrt(T))
    if option_type == "call":
        return (term1 - r * K * np.exp(-r * T) * norm.cdf(d2)) / 365.0
    else:
        return (term1 + r * K * np.exp(-r * T) * norm.cdf(-d2)) / 365.0


def vega(S, K, T, r, sigma):
    _validate_inputs(S, K, T, r, sigma)
    d1 = _d1(S, K, T, r, sigma)
    return S * norm.pdf(d1) * np.sqrt(T) / 100.0


def rho(option_type, S, K, T, r, sigma):
    _validate_inputs(S, K, T, r, sigma)
    d2 = _d2(S, K, T, r, sigma)
    if option_type == "call":
        return K * T * np.exp(-r * T) * norm.cdf(d2) / 100.0
    else:
        return -K * T * np.exp(-r * T) * norm.cdf(-d2) / 100.0


def vanna(S, K, T, r, sigma):
    _validate_inputs(S, K, T, r, sigma)
    d1 = _d1(S, K, T, r, sigma)
    d2 = _d2(S, K, T, r, sigma)
    return -norm.pdf(d1) * d2 / sigma


def vomma(S, K, T, r, sigma):
    _validate_inputs(S, K, T, r, sigma)
    d1 = _d1(S, K, T, r, sigma)
    d2 = _d2(S, K, T, r, sigma)
    v = vega(S, K, T, r, sigma)
    return v * (d1 * d2) / sigma


def charm(option_type, S, K, T, r, sigma):
    _validate_inputs(S, K, T, r, sigma)
    d1 = _d1(S, K, T, r, sigma)
    d2 = _d2(S, K, T, r, sigma)
    charm_val = -norm.pdf(d1) * (
        2.0 * r * T - d2 * sigma * np.sqrt(T)
    ) / (2.0 * T * sigma * np.sqrt(T))
    if option_type == "put":
        charm_val += r * np.exp(-r * T) * norm.cdf(-d1)
    return charm_val / 365.0


def calculate_leg_greeks(option_type, side, S, K, T, r, sigma, quantity=1):
    sign = 1.0 if side == "long" else -1.0
    return {
        "delta": sign * delta(option_type, S, K, T, r, sigma) * quantity,
        "gamma": sign * gamma(S, K, T, r, sigma) * quantity,
        "theta": sign * theta(option_type, S, K, T, r, sigma) * quantity,
        "vega": sign * vega(S, K, T, r, sigma) * quantity,
        "rho": sign * rho(option_type, S, K, T, r, sigma) * quantity,
        "vanna": sign * vanna(S, K, T, r, sigma) * quantity,
        "vomma": sign * vomma(S, K, T, r, sigma) * quantity,
        "charm": sign * charm(option_type, S, K, T, r, sigma) * quantity,
    }


def aggregate_greeks(legs_greeks):
    totals = {}
    for greeks in legs_greeks:
        for key, val in greeks.items():
            totals[key] = totals.get(key, 0.0) + val
    return totals
