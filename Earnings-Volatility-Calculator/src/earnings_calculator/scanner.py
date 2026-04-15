"""Earnings scanning orchestration and OTC ticker updater."""

import concurrent.futures
import os
import tempfile
import time
from datetime import datetime
from typing import Callable, Dict, List, Optional

import pandas as pd
import requests
import yfinance as yf
import yfinance.shared as shared

MIN_IV30_RV30_RATIO = 1.25
MAX_TERM_SLOPE = -0.00406

from earnings_calculator.cache import DataCache
from earnings_calculator.calendar import EarningsCalendarFetcher
from earnings_calculator.logging_config import create_logger
from earnings_calculator.options import OptionsAnalyzer, MIN_AVG_VOLUME


def update_otc_tickers():
    """Download OTC tickers from StockAnalysis API and write to otc-tickers.txt."""
    base_url = "https://api.stockanalysis.com/api/screener/a/f"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:135.0) "
        "Gecko/20100101 Firefox/135.0",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://stockanalysis.com/",
        "Origin": "https://stockanalysis.com",
    }
    params = {
        "m": "marketCap",
        "s": "desc",
        "c": "no,s,n,marketCap,price,change,revenue",
        "cn": "1000",
        "f": "exchangeCode-is-OTC,subtype-is-stock",
        "i": "symbols",
    }
    all_tickers = []
    page = 1
    while True:
        params["p"] = page
        response = requests.get(base_url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        page_data = data.get("data", {}).get("data", [])
        if not page_data:
            break
        for item in page_data:
            full_symbol = item.get("s", "")
            ticker = full_symbol.split("/")[-1] if "/" in full_symbol else full_symbol
            all_tickers.append(ticker)
        print(f"Processed page {page}")
        page += 1
    with tempfile.NamedTemporaryFile(mode="w", suffix=".tmp", dir=".", delete=False) as tmp:
        for ticker in all_tickers:
            tmp.write(f"{ticker}\n")
        tmp_path = tmp.name
    os.replace(tmp_path, "otc-tickers.txt")
    print("Total OTC tickers count:", len(all_tickers))
    print("OTC tickers have been written to otc-tickers.txt")


class EnhancedEarningsScanner:
    def __init__(self, analyzer: OptionsAnalyzer):
        self.analyzer = analyzer
        self.calendar_fetcher = EarningsCalendarFetcher(self.analyzer.proxy_manager)
        self.data_cache = DataCache()
        self.batch_size = 10
        self.logger = create_logger(
            "EnhancedEarningsScanner", "earnings_scanner_debug.log"
        )

    def batch_download_history(self, tickers: List[str], lean: bool = False) -> Dict[str, pd.DataFrame]:
        ticker_str = " ".join(tickers)
        try:
            for attempt in range(3):
                data = yf.download(
                    tickers=ticker_str,
                    period="2mo" if lean else "1y",
                    group_by="ticker",
                    auto_adjust=True,
                    prepost=True,
                    threads=True,
                    session=self.analyzer.session_manager.get_yf_session(),
                )

                errors = shared._ERRORS.copy() if shared._ERRORS else {}
                shared._ERRORS = {}  # reset so stale errors don't poison next call
                rate_limited = any(
                    "Too Many Requests" in str(v) or "Rate" in str(v)
                    for v in errors.values()
                )
                if rate_limited:
                    wait = 2 ** (attempt + 1)  # exponential backoff: 2s, 4s, 8s
                    self.logger.warning(f"Rate limited on batch, waiting {wait}s (attempt {attempt+1}/3)")
                    time.sleep(wait)
                    continue
                if self.analyzer.session_manager.proxy_manager.proxy_enabled and errors:
                    self.analyzer.session_manager.rotate_session()
                else:
                    break

            res = {}
            if len(tickers) == 1:
                res[tickers[0]] = data
            else:
                for tk in tickers:
                    try:
                        df = data.xs(tk, axis=1, level=0)
                        if not df.empty:
                            res[tk] = df
                    except Exception as e:
                        self.logger.debug(f"Could not extract data for {tk}: {e}")
                        continue
            return res
        except Exception as e:
            self.logger.error(f"batch download error: {e}")
            return {}

    def scan_earnings_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        progress_callback: Optional[Callable] = None,
        lean: bool = False,
    ) -> List[Dict]:
        """Scan earnings across a range of business days.

        Loops over each business day from *start_date* to *end_date*
        (inclusive), calls ``scan_earnings_stocks`` per day, injects an
        ``earnings_date`` key, and aggregates all results.
        """
        dates = pd.bdate_range(start_date, end_date)
        if dates.empty:
            return []
        all_results: List[Dict] = []
        n_dates = len(dates)
        for idx, day in enumerate(dates):
            day_dt = day.to_pydatetime()
            day_str = day_dt.strftime("%Y-%m-%d")

            def day_progress(val, _idx=idx):
                if progress_callback:
                    base = _idx / n_dates * 100
                    progress_callback(base + val / n_dates)

            results = self.scan_earnings_stocks(day_dt, day_progress, lean=lean)
            for r in results:
                r["earnings_date"] = day_str
            all_results.extend(results)
        if progress_callback:
            progress_callback(100)
        return all_results

    def scan_earnings_stocks(
        self, date: datetime, progress_callback: Optional[Callable] = None, lean: bool = False
    ) -> List[Dict]:
        ds = date.strftime("%Y-%m-%d")
        self.logger.info(f"Scan earnings for {ds}")
        e_stocks = self.calendar_fetcher.fetch_earnings_data(ds)
        try:
            with open("otc-tickers.txt", "r") as f:
                otc_tickers = {line.strip().upper() for line in f if line.strip()}
        except FileNotFoundError:
            otc_tickers = set()
        original_count = len(e_stocks)
        e_stocks = [ticker for ticker in e_stocks if ticker.upper() not in otc_tickers]
        self.logger.info(
            f"Filtered out {original_count - len(e_stocks)} OTC tickers."
        )
        if not e_stocks:
            return []
        cached_data, missing_data = self.data_cache.get_data(ds, e_stocks)
        if cached_data:
            self.logger.info(f"Using cached data for {ds}")
            raw_results = cached_data
            if missing_data:
                self.logger.info(f"{len(missing_data)} missing, attempting fill.")
                missing_tickers = [m["ticker"] for m in missing_data]
                done = 0
                total = len(missing_tickers)
                batches = [
                    missing_tickers[i : i + self.batch_size]
                    for i in range(0, total, self.batch_size)
                ]
                for b in batches:
                    hist = self.batch_download_history(b, lean=lean)
                    with concurrent.futures.ThreadPoolExecutor(
                        max_workers=1
                    ) as ex:
                        fut2stk = {
                            ex.submit(self.analyze_stock, st, hist.get(st), lean=lean): st
                            for st in b
                        }
                        for fut in concurrent.futures.as_completed(fut2stk):
                            stsym = fut2stk[fut]
                            done += 1
                            if progress_callback:
                                val = 80 + (done / total * 20)
                                progress_callback(val)
                            try:
                                r = fut.result()
                                if r:
                                    self.data_cache.update_missing_data(
                                        ds, e_stocks, r
                                    )
                            except Exception as e_:
                                self.logger.error(f"Error updating {stsym}: {e_}")
                cached_data, _ = self.data_cache.get_data(ds, e_stocks)
                raw_results = cached_data
            if progress_callback:
                progress_callback(100)
            return raw_results
        recommended = []
        total_stocks = len(e_stocks)
        done = 0
        batches = [
            e_stocks[i : i + self.batch_size]
            for i in range(0, total_stocks, self.batch_size)
        ]
        for idx_b, b in enumerate(batches):
            if idx_b > 0:
                time.sleep(1)  # throttle between batches to avoid rate limit
            hist_map = self.batch_download_history(b, lean=lean)
            # Pre-filter: skip stocks that can't pass volume/price minimums
            # This avoids options chain fetches on illiquid/penny stocks
            qualified = []
            for st in b:
                hdf = hist_map.get(st)
                if hdf is None or hdf.empty:
                    self.logger.debug(f"Pre-filter skip {st}: no history data")
                    continue
                try:
                    avg_vol = hdf["Volume"].rolling(30, min_periods=5).mean().dropna().iloc[-1] if "Volume" in hdf.columns else 0
                except (IndexError, KeyError):
                    self.logger.debug(f"Pre-filter skip {st}: insufficient volume data")
                    continue
                if avg_vol >= MIN_AVG_VOLUME:
                    qualified.append(st)
                else:
                    self.logger.debug(f"Pre-filter skip {st}: avg_vol={avg_vol:,.0f} < {MIN_AVG_VOLUME:,}")
            skipped = len(b) - len(qualified)
            self.logger.info(f"Batch {idx_b}: {len(b)} stocks → {len(qualified)} qualified, {skipped} skipped")
            done += skipped  # count skipped stocks as processed for progress
            if not qualified:
                continue
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=min(1, len(qualified))
            ) as ex:
                fut2stk = {
                    ex.submit(self.analyze_stock, st, hist_map.get(st), lean=lean): st
                    for st in qualified
                }
                for ft in concurrent.futures.as_completed(fut2stk):
                    st = fut2stk[ft]
                    done += 1
                    if progress_callback:
                        # Fixed: calculate progress WITHOUT recalculating skips per stock
                        pc = done / total_stocks * 80
                        progress_callback(pc)
                    try:
                        r = ft.result()
                        # Skip error dicts from failed analyses, don't cache failures
                        if r and "error" not in r:
                            recommended.append(r)
                    except Exception as e_:
                        self.logger.error(f"Error processing future result: {e_}")
        recommended.sort(
            key=lambda x: (
                x["recommendation"] != "Recommended",
                x["earnings_time"] == "Unknown",
                x["earnings_time"],
                x["ticker"],
            )
        )
        # Include Avoid stubs for pre-filtered (skipped) stocks so the cache
        # knows they were evaluated and won't re-analyze them on the next run.
        analyzed_tickers = {r["ticker"] for r in recommended}
        for st in e_stocks:
            if st not in analyzed_tickers:
                recommended.append({
                    "ticker": st,
                    "sector": "Unknown",
                    "current_price": 0,
                    "market_cap": 0,
                    "volume": 0,
                    "avg_volume": False,
                    "avg_volume_value": 0,
                    "earnings_time": self.calendar_fetcher.get_earnings_time(st),
                    "recommendation": "Avoid",
                    "expected_move": "N/A",
                    "atr14": 0,
                    "atr14_pct": 0,
                    "iv30_rv30": -1,  # sentinel: -1 = pre-filtered, 0 = rate-limited
                    "term_slope": 0,
                    "term_structure": 0,
                    "historical_volatility": 0,
                    "current_iv": None,
                    "iv_rank": None,
                })
        self.data_cache.save_data(ds, e_stocks, recommended)
        if progress_callback:
            progress_callback(100)
        return recommended

    def analyze_stock(
        self,
        ticker: str,
        history_data: Optional[pd.DataFrame] = None,
        skip_otc_check: bool = False,
        lean: bool = False,
    ) -> Optional[Dict]:
        try:
            st2 = self.analyzer.get_ticker(ticker)
            if not skip_otc_check:
                exchange = st2.info.get("exchange", "")
                otc_exchanges = {"PNK", "Other OTC", "OTC", "GREY"}
                if exchange in otc_exchanges:
                    self.logger.info(
                        f"[SKIP] Ticker '{ticker}' is OTC (exchange='{exchange}')."
                    )
                    return None
            if history_data is None or history_data.empty:
                hd = st2.history(period="2mo" if lean else "1y")
                if hd.empty:
                    hd = st2.history(period="5d")
                if hd.empty:
                    self.logger.warning(f"No data for {ticker}; skipping.")
                    return None
                history_data = hd

            if isinstance(history_data.columns, pd.MultiIndex):
                history_data.columns = history_data.columns.get_level_values(1)
            if "Close" in history_data.columns:
                cp = history_data["Close"].iloc[-1]
            elif "Adj Close" in history_data.columns:
                cp = history_data["Adj Close"].iloc[-1]
            else:
                raise ValueError("No close price data available.")
            voldata = history_data["Volume"]
            hv = self.analyzer.yang_zhang_volatility(history_data)
            tv = voldata.iloc[-1] if not voldata.empty else 0
            od = self.analyzer.compute_recommendation(ticker, history_data=history_data, lean=lean)
            if isinstance(od, dict) and "error" not in od:
                avb = od["avg_volume"]
                ivcheck = od["iv30_rv30"] >= MIN_IV30_RV30_RATIO
                slopecheck = od["term_slope"] <= MAX_TERM_SLOPE
                if avb and ivcheck and slopecheck:
                    rec = "Recommended"
                elif slopecheck and ((avb and not ivcheck) or (ivcheck and not avb)):
                    rec = "Consider"
                else:
                    rec = "Avoid"
                return {
                    "ticker": ticker,
                    "sector": st2.info.get("sector", "Unknown"),
                    "current_price": cp,
                    "market_cap": st2.info.get("marketCap", 0),
                    "volume": tv,
                    "avg_volume": avb,
                    "avg_volume_value": od.get("avg_volume_value", 0),
                    "earnings_time": self.calendar_fetcher.get_earnings_time(ticker),
                    "recommendation": rec,
                    "expected_move": od.get("expected_move", "N/A"),
                    "atr14": od.get("atr14", 0),
                    "atr14_pct": od.get("atr14_pct", 0),
                    "iv30_rv30": od.get("iv30_rv30", 0),
                    "term_slope": od.get("term_slope", 0),
                    "term_structure": od.get("term_structure", 0),
                    "historical_volatility": hv,
                    "current_iv": od.get("current_iv", None),
                    "iv_rank": od.get("iv_rank", None),
                }
            return {
                "ticker": ticker,
                "sector": st2.info.get("sector", "Unknown"),
                "current_price": cp,
                "market_cap": 0,
                "volume": tv,
                "avg_volume": False,
                "avg_volume_value": 0,
                "earnings_time": self.calendar_fetcher.get_earnings_time(ticker),
                "recommendation": "Avoid",
                "expected_move": "N/A",
                "atr14": 0,
                "atr14_pct": 0,
                "iv30_rv30": 0,
                "term_slope": 0,
                "term_structure": 0,
                "historical_volatility": hv,
                "current_iv": None,
                "iv_rank": None,
            }
        except Exception as e:
            self.logger.error(f"Analyze error for {ticker}: {e}")
            return None
