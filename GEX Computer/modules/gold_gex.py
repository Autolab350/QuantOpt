import sys
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime
import numpy as np

# Path to OptLib
sys.path.append('/home/jack/Documents/Workshop/OptLib')
from computer import calculate_risk

def run_gold_analysis():
    # 1. LIVE GOLD SPOT (DIRECT)
    gc = yf.Ticker("GC=F")
    spot_gold = gc.fast_info['lastPrice']
    print(f"LIVE GOLD SPOT (/GC): ${spot_gold:,.2f}")

    # 2. GLD PROXY SCALING
    gld = yf.Ticker("GLD")
    gld_spot = gld.fast_info['lastPrice']
    
    # Calculate exact Real-Time Ratio (No guessing)
    ratio = spot_gold / gld_spot
    print(f"Current Gold/GLD Ratio: {ratio:,.4f}")

    # 3. FETCH FULL GLD CHAIN (PROXY FOR FUTURES OPTION DATA)
    print("Fetching full option chain...")
    expirations = gld.options
    all_options = []
    today = datetime.now()

    for exp in expirations:
        try:
            chain = gld.option_chain(exp)
            T = max((datetime.strptime(exp, '%Y-%m-%d') - today).days / 365.25, 0.002)
            for df, otype in [(chain.calls, 'c'), (chain.puts, 'p')]:
                df = df.copy()
                df['type'] = otype
                df['T'] = T
                all_options.append(df)
        except: pass
    
    df_full = pd.concat(all_options, ignore_index=True)
    df_full['strike_gold'] = df_full['strike'] * ratio
    
    # 4. CALC TOTAL GEX
    print(f"Calculating GEX on {len(df_full)} contracts across the entire curve...")
    total_gex = 0.0
    for _, row in df_full[df_full.openInterest > 0].iterrows():
        iv = row['impliedVolatility'] if row['impliedVolatility'] > 0 else 0.15
        # Pass the TRUE /GC Gold Spot to the Greek Engine
        res = calculate_risk("GC", spot_gold, row['strike_gold'], row['T'], 0.05, iv, row['type'])
        ga = float(res.get('gamma', 0.0) or 0.0)
        dg = ga if row['type'] == 'c' else -ga
        # Note: Gold Future Contract has 100oz. GLD option is 100 shares.
        # This proxy assumes dealers hedge GLD deltas which flow back to spot gold.
        gex = dg * float(row['openInterest']) * 100.0 * (spot_gold**2) * 0.01
        total_gex += gex

    print(f"\n==> FINAL GOLD GEX: ${total_gex:,.0f}")
    
    # 5. SIMULATE GOLD GAMMA FLIP
    print("\nSimulating /GC price movements to find Gamma Flip...")
    levels = np.arange(spot_gold - 75, spot_gold + 75, 5)
    flip = None
    prev_g = None
    
    for p in levels:
        sim_gex = 0.0
        # Only check nearby strikes for simulation performance
        relevant = df_full[(df_full.strike_gold > p * 0.95) & (df_full.strike_gold < p * 1.05)]
        for _, row in relevant.iterrows():
            iv = row['impliedVolatility'] if row['impliedVolatility'] > 0 else 0.15
            res = calculate_risk("GC", p, row['strike_gold'], row['T'], 0.05, iv, row['type'])
            ga = float(res.get('gamma', 0.0) or 0.0)
            dg = ga if row['type'] == 'c' else -ga
            sim_gex += dg * float(row['openInterest']) * 100.0 * (p**2) * 0.01
        
        if prev_g is not None and prev_g * sim_gex < 0:
            flip = p - 2.5
        prev_g = sim_gex
        
    if flip:
        print(f"==> GOLD GAMMA FLIP LEVEL: ${flip:,.2f}")
    else:
        print("Gold Flip not found in local +/- $75 range.")

if __name__ == "__main__":
    run_gold_analysis()
