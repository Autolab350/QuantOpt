import pandas as pd
import numpy as np
import sys
from datetime import datetime

# Connect OptLib
sys.path.append('/home/jack/Documents/Workshop/OptLib')
from computer import calculate_risk

def run_gex_analysis(filename):
    # Read the header info
    with open(filename, 'r') as f:
        lines = f.readlines()
    
    # Line 0: Standard & Poors 500 Index,Last: 6,823.7000,Change: N/A
    spot_line = lines[0]
    spot_price = float(spot_line.split('Last:')[1].split(',')[0].strip())
    print(f"Parsed SPX Spot from CSV: {spot_price}")

    # Load the data, skipping header lines
    df = pd.read_csv(filename, skiprows=2)
    
    # The CSV has Calls and Puts side-by-side
    # Columns: Expiration Date, Calls, Last Sale, Net, Bid, Ask, Volume, IV, Delta, Gamma, Open Interest, Strike, Puts, Last Sale, Net, Bid, Ask, Volume, IV, Delta, Gamma, Open Interest
    
    today = datetime.now()
    total_gex = 0.0

    # Process Calls
    calls = df[['Expiration Date', 'Strike', 'IV', 'Gamma', 'Open Interest']].copy()
    calls['type'] = 'c'
    
    # Process Puts
    # Note: Puts data starts after the Strike column. Based on the header:
    # Strike is col 11 (0-indexed). Puts specific data starts at col 12.
    # col 18 is IV (put), col 19 is Delta (put), col 20 is Gamma (put), col 21 is OI (put)
    puts = df.iloc[:, [0, 11, 18, 20, 21]].copy()
    puts.columns = ['Expiration Date', 'Strike', 'IV', 'Gamma', 'Open Interest']
    puts['type'] = 'p'
    
    all_options = pd.concat([calls, puts], ignore_index=True)
    
    print(f"Processing {len(all_options)} total option contracts from CSV...")

    for _, row in all_options.iterrows():
        try:
            oi = float(row['Open Interest'])
            if oi <= 0 or pd.isna(oi):
                continue
                
            strike = float(row['Strike'])
            # Use Gamma from CSV or recalculate if possible. CSV Gamma is often more reliable but let's check.
            gamma = float(row['Gamma'])
            
            # GEX = Gamma * OI * 100 * Spot^2 * 0.01
            # Dealer Long Calls (+), Dealer Short Puts (-)
            dg = gamma if row['type'] == 'c' else -gamma
            gex = dg * oi * 100.0 * (spot_price**2) * 0.01
            total_gex += gex
        except:
            continue

    print(f"\n==> FINAL SPX GEX (from CSV): ${total_gex:,.0f}")
    
    # Simulating Gamma Flip using the CSV data as a baseline
    print("\nSimulating Gamma Flip Level...")
    levels = np.arange(spot_price - 150, spot_price + 150, 15)
    flip = None
    prev_g = None
    
    for p in levels:
        sim_gex = 0.0
        for _, row in all_options.iterrows():
            try:
                oi = float(row['Open Interest'])
                if oi <= 0: continue
                
                strike = float(row['Strike'])
                exp_date = datetime.strptime(row['Expiration Date'], '%Y-%m-%d')
                T = max((exp_date - today).days / 365.25, 0.002)
                iv = float(row['IV']) if float(row['IV']) > 0 else 0.15
                
                # RE-CALCULATE Gamma for each simulated price level using OptLib
                res = calculate_risk("SPX", p, strike, T, 0.05, iv, row['type'])
                ga = float(res.get('gamma', 0.0) or 0.0)
                
                dg = ga if row['type'] == 'c' else -ga
                sim_gex += dg * oi * 100.0 * (p**2) * 0.01
            except:
                continue
        
        if prev_g is not None and prev_g * sim_gex < 0:
            flip = p - 7.5
        prev_g = sim_gex
        
    if flip:
        print(f"==> Estimated Gamma Flip Level: {flip:.2f}")
    else:
        print("Gamma Flip not found in +/- 150pt range.")

if __name__ == "__main__":
    run_gex_analysis('spx_quotedata.csv')
