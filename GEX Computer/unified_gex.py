import sys
import os
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import scipy.optimize as opt
from scipy.stats import norm

# --- SYSTEMATIC ARCHITECTURE ---
# This engine handles ES=F (S&P 500) and GC=F (Gold) using unified scaling.
# Integrates OptLib institutional-grade Greeks.

# Connect OptLib
sys.path.append('/home/jack/Documents/Workshop/OptLib')
try:
    from computer import calculate_risk
    HAS_OPTLIB = True
except ImportError:
    HAS_OPTLIB = False

# Asset Configs: (Ticker, Proxy, Multiplier, Scan Range %, Increment)
ASSET_MAP = {
    'ES': ('ES=F', 'SPY', 100, 0.05, 1.0), # ES contract multiplier is 50, but we use 100 here to match SPY proxy scaling (10x SPY * 10 multiplier)
    'GC': ('GC=F', 'IAU', 100, 0.10, 5.0)
}

def get_bs_gamma(S, K, T, r, sigma, ticker="SPX"):
    if T <= 0 or sigma <= 0 or S <= 0: return 0
    if HAS_OPTLIB:
        # Use institutional OptLib computer
        res = calculate_risk(ticker, S, K, T, r, sigma, 'c')
        return res.get('gamma', 0.0)
    # Fallback to standard math
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    return norm.pdf(d1) / (S * sigma * np.sqrt(T))

def get_iv(price, S, K, T, r, option_type, ticker="SPX"):
    if T <= 0 or price <= 0: return 0.15
    def objective(sigma):
        if HAS_OPTLIB:
            res = calculate_risk(ticker, S, K, T, r, sigma, option_type)
            return res['value'] - price
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        if option_type == 'call':
            res = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        else:
            res = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        return res - price
    try:
        return opt.brentq(objective, 1e-5, 5.0)
    except:
        return 0.15

def run_unified_gex(asset_key):
    ticker_str, proxy_str, multiplier, scan_pct, scan_step = ASSET_MAP[asset_key]
    
    print(f"\n--- UNIFIED GEX ENGINE: {asset_key} ({ticker_str}) ---")
    if HAS_OPTLIB:
        print("Sourcing math from OptLib (Institutional Grade)")
    
    # 1. Fetch Spot Prices
    f_ticker = yf.Ticker(ticker_str)
    p_ticker = yf.Ticker(proxy_str)

    
    f_spot = f_ticker.history(period="1d")['Close'].iloc[-1]
    p_spot = p_ticker.history(period="1d")['Close'].iloc[-1]
    basis = f_spot / p_spot
    
    print(f"Spot: {f_spot:.2f} | Proxy: {p_spot:.2f} | Basis: {basis:.4f}")

    # 2. RVOL Analysis
    hist = f_ticker.history(period="21d")
    rvol = hist['Volume'].iloc[-1] / hist['Volume'].iloc[:-1].mean()
    print(f"RVOL: {rvol:.2f} ({'QUIET' if rvol < 0.8 else 'ACTIVE' if rvol > 1.5 else 'NORMAL'})")

    # 3. Chains & Greeks
    expirations = p_ticker.options[:4]
    r = 0.045
    now = datetime.now()
    position_data = []

    for exp in expirations:
        chain = p_ticker.option_chain(exp)
        t_days = (datetime.strptime(exp, '%Y-%m-%d') - now).days
        T = max(t_days, 0.5) / 365.0

        for df, opt_type in [(chain.calls, 'call'), (chain.puts, 'put')]:
            for _, row in df.iterrows():
                strike_p = row['strike']
                oi = row['openInterest']
                if oi < 10 or abs(strike_p - p_spot) / p_spot > 0.08: continue

                bid, ask = row['bid'], row['ask']
                mid = (bid + ask) / 2 if (bid > 0 and ask > 0) else row['lastPrice']
                iv = get_iv(mid, p_spot, strike_p, T, r, opt_type)
                
                position_data.append({
                    'strike_f': strike_p * basis,
                    'strike_p': strike_p,
                    'oi': oi, 'T': T, 'iv': iv, 'type': opt_type
                })

    # 4. Brute-Force Scanner (Unified)
    # Ensure current spot is included in scan range
    scan_start = f_spot * (1 - scan_pct)
    scan_end = f_spot * (1 + scan_pct)
    scan_range = np.arange(scan_start, scan_end, scan_step)
    # Add actual current spot to ensure [nan] avoidance
    scan_range = np.sort(np.append(scan_range, f_spot))
    gex_points = []

    for test_s_f in scan_range:
        test_s_p = test_s_f / basis
        net_gex = 0
        for item in position_data:
            gamma_p = get_bs_gamma(test_s_p, item['strike_p'], item['T'], r, item['iv'])
            if np.isnan(gamma_p): gamma_p = 0
            # GEX = Gamma * OI * Mult * S^2 * 0.01
            gex = gamma_p * item['oi'] * multiplier * (test_s_f**2) * 0.01
            if item['type'] == 'put': gex *= -1
            if not np.isnan(gex):
                net_gex += gex
        gex_points.append((test_s_f, net_gex))

    # 5. Flip & Walls Detection
    flip = None
    for i in range(1, len(gex_points)):
        p1, g1 = gex_points[i-1]
        p2, g2 = gex_points[i]
        if (g1 <= 0 and g2 > 0) or (g1 >= 0 and g2 < 0):
            flip = p1 + (0 - g1) * (p2 - p1) / (g2 - g1)
            break
            
    # Find current GEX
    # Match the specific spot we just added to the range
    cur_gex_matches = [g for s, g in gex_points if s == f_spot]
    # Fallback to nearest if exact match for floating point fails
    if not cur_gex_matches:
        cur_gex_matches = [g for s, g in gex_points if abs(s - f_spot) <= 0.0001]
    
    cur_gex = cur_gex_matches[0] if cur_gex_matches else 0

    print(f"\nNET GEX: ${cur_gex / 1e9:.2f} Billion")
    if flip:
        print(f"GAMMA FLIP: {flip:.2f} ({((flip/f_spot)-1)*100:+.2f}%)")
    else:
        print("GAMMA FLIP: Not in cluster (+/- 5%)")

    print("TOP WALLS:")
    position_data.sort(key=lambda x: x['oi'], reverse=True)
    for w in position_data[:3]:
        print(f"Strike {w['strike_f']:.0f} | OI: {w['oi']} | {w['type'].upper()}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python unified_gex.py [ES|GC]")
    else:
        run_unified_gex(sys.argv[1].upper())
