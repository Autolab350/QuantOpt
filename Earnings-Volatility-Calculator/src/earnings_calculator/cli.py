"""Simple CLI for Earnings Volatility Calculator - no GUI, just terminal output."""

import argparse
import os
import warnings
from datetime import datetime, timedelta
from tabulate import tabulate
import yfinance as yf
from earnings_calculator.scanner import EnhancedEarningsScanner
from earnings_calculator.options import OptionsAnalyzer
from earnings_calculator.proxy import ProxyManager

# Sector → representative ETF mapping
SECTOR_ETFS = {
    "Technology": "QQQ",
    "Communication Services": "XLC",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Energy": "XLE",
    "Financial Services": "XLF",
    "Healthcare": "XLV",
    "Industrials": "XLI",
    "Basic Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
}


def get_etf_iv(ticker_sym: str) -> float:
    """Get nearest ATM IV for an ETF ticker. Returns 0.0 on failure."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            t = yf.Ticker(ticker_sym)
            if not t.options:
                return 0.0
            exp = t.options[0]
            chain = t.option_chain(exp)
            hist = t.history(period="5d")
            if hist.empty:
                return 0.0
            price = hist["Close"].iloc[-1]
            calls = chain.calls
            idx = (calls["strike"] - price).abs().idxmin()
            return float(calls.loc[idx, "impliedVolatility"])
    except Exception:
        return 0.0


def main():
    """Run scan for earnings and print results."""
    import json
    import csv
    import sys
    
    parser = argparse.ArgumentParser(description="Earnings Volatility Calculator CLI")
    parser.add_argument("--full", action="store_true", help="Full mode: 1yr history, all expirations (slower)")
    parser.add_argument("--days", type=int, default=10, help="Days ahead to scan (default: 10)")
    parser.add_argument("--no-cache", action="store_true", help="Ignore and overwrite cached results")
    parser.add_argument("--filter", choices=["all", "recommended", "consider"], default="recommended", 
                       help="Filter by recommendation (default: recommended)")
    parser.add_argument("--format", choices=["table", "json", "csv", "text"], default="text",
                       help="Output format (default: text)")
    args = parser.parse_args()
    lean = not args.full

    if args.no_cache:
        import shutil, glob
        cache_dir = "stock_cache"
        if os.path.exists(cache_dir):
            for f in glob.glob(os.path.join(cache_dir, "*.pkl")):
                try:
                    os.remove(f)
                except Exception as e:
                    print(f"Warning: couldn't remove {f}: {e}", file=sys.stderr)
            print(f"Cache cleared ({cache_dir}).", file=sys.stderr)
        else:
            print(f"No cache directory found ({cache_dir}).", file=sys.stderr)

    print("Earnings Volatility Calculator - CLI Mode", file=sys.stderr)
    print("=" * 80, file=sys.stderr)
    print(f"Mode: {'LEAN (fast)' if lean else 'FULL (thorough)'}", file=sys.stderr)

    # Setup
    proxy_manager = ProxyManager()
    proxy_manager.proxy_enabled = False
    analyzer = OptionsAnalyzer(proxy_manager)
    scanner = EnhancedEarningsScanner(analyzer)

    today = datetime.now()
    end_date = today + timedelta(days=args.days)
    print(f"Scanning earnings from {today.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}", file=sys.stderr)

    def progress_callback(pct):
        print(f"\rProgress: {pct:.0f}%", end="", flush=True, file=sys.stderr)

    results = scanner.scan_earnings_date_range(today, end_date, progress_callback, lean=lean)
    print("\n", file=sys.stderr)

    if not results:
        print("No earnings found.", file=sys.stderr)
        return

    # Filter results
    if args.filter == "recommended":
        filtered = [r for r in results if r.get("recommendation") == "Recommended"]
    elif args.filter == "consider":
        filtered = [r for r in results if r.get("recommendation") in ["Recommended", "Consider"]]
    else:
        filtered = results

    # Fetch sector ETF IVs only for sectors that have stocks in the filtered set
    etf_ivs = {}
    if filtered:
        sectors_present = {r.get("sector", "Unknown") for r in filtered}
        needed_etfs = {SECTOR_ETFS[s] for s in sectors_present if s in SECTOR_ETFS}
        if needed_etfs:
            print(f"Fetching sector ETF IVs ({', '.join(sorted(needed_etfs))})...", file=sys.stderr)
            for etf in needed_etfs:
                etf_ivs[etf] = get_etf_iv(etf)

    def sector_signal(r) -> str:
        sector = r.get("sector", "Unknown")
        etf = SECTOR_ETFS.get(sector)
        if not etf or etf not in etf_ivs or etf_ivs[etf] == 0.0:
            return "?"
        stock_iv = r.get("current_iv") or 0.0
        etf_iv = etf_ivs[etf]
        if stock_iv == 0.0:
            return "?"
        ratio = stock_iv / etf_iv
        if ratio >= 1.20:
            return f"↑ vs {etf}"
        elif ratio <= 0.85:
            return f"↓ vs {etf}"
        else:
            return f"~ {etf}"

    # Output format
    if args.format == "json":
        for r in filtered:
            r["sector_signal"] = sector_signal(r)
            r["sector_etf"] = SECTOR_ETFS.get(r.get("sector", ""), "N/A")
        print(json.dumps(filtered, indent=2))
    elif args.format == "csv":
        if filtered:
            for r in filtered:
                r["sector_signal"] = sector_signal(r)
                r["sector_etf"] = SECTOR_ETFS.get(r.get("sector", ""), "N/A")
            writer = csv.DictWriter(sys.stdout, fieldnames=filtered[0].keys())
            writer.writeheader()
            writer.writerows(filtered)
    elif args.format == "table":
        rows = []
        for r in filtered:
            rows.append([
                r.get("ticker", "N/A"),
                r.get("sector", "Unknown")[:12],
                r.get("recommendation", "N/A"),
                f"${r.get('current_price', 0):.2f}",
                f"{r.get('iv30_rv30', 0):.2f}" if r.get('iv30_rv30') else "N/A",
                f"{r.get('term_slope', 0):.4f}" if r.get('term_slope') is not None else "N/A",
                sector_signal(r),
                r.get('earnings_time', "Unknown"),
            ])
        headers = ["Ticker", "Sector", "Rec", "Price", "IV/RV", "Term", "vs ETF", "Time"]
        print(tabulate(rows, headers=headers, tablefmt="grid"))
    else:  # text (default)
        print(f"{'Ticker':<8} {'Sector':<18} {'Rec':<13} {'Price':>8} {'IV/RV':>6} {'Term':>8} {'vs ETF':<14} {'Time':<12}")
        print("-" * 95)
        # Group by sector
        from itertools import groupby
        sorted_filtered = sorted(filtered, key=lambda x: (x.get("sector", "Unknown"), x.get("ticker", "")))
        for sector, group in groupby(sorted_filtered, key=lambda x: x.get("sector", "Unknown")):
            for r in group:
                sig = sector_signal(r)
                print(f"{r.get('ticker','N/A'):<8} {sector[:18]:<18} {r.get('recommendation','N/A'):<13} "
                      f"${r.get('current_price', 0):<7.2f} {r.get('iv30_rv30', 0):<6.2f} "
                      f"{r.get('term_slope', 0):<8.4f} {sig:<14} {r.get('earnings_time','Unknown'):<12}")

    # Summary to stderr
    summary = {}
    for r in filtered:
        rec = r.get("recommendation", "Unknown")
        summary[rec] = summary.get(rec, 0) + 1

    print(f"\nFiltered: {len(filtered)} out of {len(results)} stocks", file=sys.stderr)
    print("Summary:", file=sys.stderr)
    for rec, count in sorted(summary.items()):
        print(f"  {rec}: {count}", file=sys.stderr)


if __name__ == "__main__":
    main()
