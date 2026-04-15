import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
from strategy_definitions import suggest_strategies, GREEK_TOOLTIPS, get_all_strategies
from risk_calculator import (
    full_risk_report,
    calculate_payoff_curve,
)

st.set_page_config(page_title="Strategy Advisor", layout="wide")
st.title("Strategy Advisor")
st.caption("Select your Greek preferences and market parameters. The system will recommend strategies, calculate real Greeks, and show the full risk anatomy.")

# --- Sidebar: Market Parameters ---
with st.sidebar:
    st.header("Market Parameters")
    S0 = st.number_input("Current Price (S)", value=100.0, min_value=0.01, step=1.0)
    K = st.number_input("Strike Price (K)", value=100.0, min_value=0.01, step=1.0)
    T_days = st.number_input("Days to Expiration", value=30, min_value=1, step=1)
    T = T_days / 365.0
    sigma = st.number_input("Implied Volatility (IV)", value=0.20, min_value=0.01, max_value=5.0, step=0.01)
    r = st.number_input("Risk-Free Rate", value=0.05, min_value=0.0, max_value=1.0, step=0.01)
    spread_width = st.number_input("Spread Width ($)", value=5.0, min_value=1.0, step=1.0)

    st.header("Greek Tooltips")
    for greek, tip in GREEK_TOOLTIPS.items():
        with st.expander(greek.capitalize()):
            st.write(tip)

# --- Main: Greek Preferences ---
st.subheader("Your Greek Preferences")
choices = ["positive", "negative", "neutral", "any"]
col1, col2, col3, col4, col5 = st.columns(5)
user_prefs = {}
with col1:
    user_prefs["Delta"] = st.selectbox("Delta", choices, index=3)
with col2:
    user_prefs["Gamma"] = st.selectbox("Gamma", choices, index=3)
with col3:
    user_prefs["Vega"] = st.selectbox("Vega", choices, index=3)
with col4:
    user_prefs["Theta"] = st.selectbox("Theta", choices, index=3)
with col5:
    user_prefs["Rho"] = st.selectbox("Rho", choices, index=3)

submitted = st.button("Analyze Strategies")

if submitted:
    top_matches = suggest_strategies(user_prefs, S0, K, T, r, sigma, spread_width)

    if not top_matches:
        st.warning("No strategies matched your preferences.")
    else:
        # --- Match Score Chart ---
        st.subheader("Top Recommended Strategies")
        names = [m[1] for m in top_matches]
        scores = [m[0] for m in top_matches]

        fig_score, ax_score = plt.subplots(figsize=(8, 3))
        bars = ax_score.barh(names[::-1], scores[::-1], color="#4a90d9")
        ax_score.set_xlim(0, 1.1)
        ax_score.set_xlabel("Match Score")
        for bar, score in zip(bars, scores[::-1]):
            ax_score.text(
                bar.get_width() + 0.02,
                bar.get_y() + bar.get_height() / 2,
                f"{score:.0%}",
                va="center",
            )
        st.pyplot(fig_score)

        # --- Detailed Analysis Per Strategy ---
        for match_score, name, strat in top_matches:
            st.markdown("---")
            st.subheader(f"{name} ({strat.category.upper()})")
            st.write(strat.description)

            report = full_risk_report(strat, S0, T, r, sigma)

            # Risk Metrics
            rc1, rc2, rc3, rc4 = st.columns(4)
            rc1.metric("Max Profit", f"${report['max_profit']:.2f}")
            rc2.metric("Max Loss", f"${report['max_loss']:.2f}")
            rc3.metric("Profit Area", f"{report['profit_area_pct']:.1f}%")
            rc4.metric("Capital Required", f"${report['capital_required']:.2f}")

            rc5, rc6, rc7 = st.columns(3)
            rc5.metric("Net Premium", f"${report['net_premium']:.2f}")
            rc6.metric("Risk/Reward", f"{report['risk_reward_ratio']:.2f}")
            be_str = ", ".join([f"${b}" for b in report["breakeven_points"]]) or "N/A"
            rc7.metric("Breakevens", be_str)

            # Legs Table
            with st.expander("Option Legs"):
                for leg in report["legs"]:
                    side_label = "BUY" if leg["side"] == "long" else "SELL"
                    st.write(
                        f"{side_label} {leg['quantity']}x {leg['type'].upper()} @ ${leg['strike']}"
                    )

            # Greeks Table
            with st.expander("Greeks (Calculated)"):
                g = report["greeks"]
                gc1, gc2, gc3, gc4 = st.columns(4)
                gc1.metric("Delta", f"{g['delta']:.4f}")
                gc2.metric("Gamma", f"{g['gamma']:.6f}")
                gc3.metric("Theta", f"{g['theta']:.4f}")
                gc4.metric("Vega", f"{g['vega']:.4f}")

                gc5, gc6, gc7, gc8 = st.columns(4)
                gc5.metric("Rho", f"{g['rho']:.4f}")
                gc6.metric("Vanna", f"{g['vanna']:.4f}")
                gc7.metric("Vomma", f"{g['vomma']:.4f}")
                gc8.metric("Charm", f"{g['charm']:.6f}")

            # Payoff Chart
            with st.expander("Payoff Curve"):
                S_range, payoffs = calculate_payoff_curve(strat, S0, T, r, sigma)
                fig_pay, ax_pay = plt.subplots(figsize=(8, 4))
                ax_pay.plot(S_range, payoffs, color="#4a90d9", linewidth=2)
                ax_pay.axhline(0, color="gray", linewidth=0.5, linestyle="--")
                ax_pay.axvline(S0, color="red", linewidth=0.5, linestyle="--", label=f"Current: ${S0}")
                for be in report["breakeven_points"]:
                    ax_pay.axvline(be, color="orange", linewidth=0.5, linestyle=":", label=f"BE: ${be}")
                ax_pay.fill_between(S_range, payoffs, 0, where=(payoffs > 0), alpha=0.15, color="green")
                ax_pay.fill_between(S_range, payoffs, 0, where=(payoffs < 0), alpha=0.15, color="red")
                ax_pay.set_xlabel("Price at Expiration")
                ax_pay.set_ylabel("Profit / Loss ($)")
                ax_pay.set_title(f"{name} Payoff")
                ax_pay.legend(fontsize=8)
                st.pyplot(fig_pay)

            # Explanation
            with st.expander("Why This Strategy"):
                explanation = strat.get_explanation(S0, T, r, sigma)
                st.write(explanation)
