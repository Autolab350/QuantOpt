
GEX - GAMMA EXPOSURE TRADING SYSTEM

What is GEX?

Dealers sell options to clients and immediately buy futures to delta-hedge. As market price moves, delta changes, forcing dealers to rehedge constantly. This mechanical hedging creates predictable price support and resistance levels.

When GEX is positive, dealers are SHORT gamma. They're forced to sell on rallies and buy on dips. This pushes price downward. When GEX is negative, dealers are LONG gamma. They're forced to buy on rallies and sell on dips. This pushes price upward.

GEX is not opinion. It's physics. Dealers have no choice.

The Gamma Flip Level

The flip level is where dealer hedging direction changes. Above the flip, dealers SHORT gamma (bearish). Below the flip, dealers LONG gamma (bullish). When price approaches the flip, dealers are locked in. That level becomes strong support or resistance. This is where trades work.

Confidence

Confidence measures how much gamma is concentrated at specific levels. Higher confidence means dealers are stacked. Lower confidence means their positioning is scattered.

5-30% confidence: Skip it. Signal is weak.
50-70% confidence: Medium signal. Only trade if other engines agree.
80%+ confidence: Trade it. Strong dealer positioning.

Current Problem

We're using SPY options (82 strikes). Real SPX has 9,800+ strikes. This fragments the signal. Our confidence dropped from potential 80% to actual 5%. We need real SPX data.

How to Trade GEX

Spot 6,855 is current price. Gamma Flip is 6,429. GEX is +124B.

If confidence was 80%:
- SHORT at 6,855
- Target: 6,429 (flip level)
- Stop loss: 6,950 (100 points above entry)

With 1 micro ES contract:
- $5 per point, so 20-30 point move = $100-150 profit
- 100 point stop = $500 loss
- Risk/Reward: 1:3 at best

This only works with 70%+ win rate. Current confidence is 5%. Don't trade it.

Expected Value Math

At 60% win rate with $100 wins and $500 stops:
60 wins x $100 = $6,000
40 losses x -$500 = -$20,000
Net: -$14,000 per 100 trades. Skip it.

At 75% win rate:
75 wins x $100 = $7,500
25 losses x -$500 = -$12,500
Net: -$5,000 still losing. Need tighter stops or bigger wins.

This is why we need all 4 engines. GEX alone can't carry the whole strategy.

Multi-Market Use

GEX works on gold (GC), crude (CL), currencies, any options market. Gold is interesting because it has institutional order blocks. When an institutional order block level matches the gamma flip level, that's double confirmation. 85%+ edge territory.

Order Blocks and Gamma Flip

Order block: Institution placed a large order at that level. If price comes back, they defend or re-enter. Discretionary.

Gamma flip: Dealers are mechanically forced to flip hedging at that level. No choice.

When they coincide, you have mechanical force plus institutional memory. That's the setups that work.

Stop Loss and Take Profit

Simple version:
- TP at flip level
- SL: 50-100 points above entry based on volatility

Better version:
- Use ATR to set dynamic SL
- Use Greeks to calculate probability of hitting target

The Four Engine Strategy

GEX alone: 5-30% confidence
GEX + Vol: 45-55% confidence
GEX + Vol + Greeks: 60-70% confidence
GEX + Vol + Greeks + Order Blocks: 75-90% confidence

One engine doesn't work. That's why there are four.

Key Rules

1. Dealers must hedge. It's mechanical. No discretion.
2. The flip level is real support/resistance.
3. Confidence = signal strength. It does NOT guarantee wins.
4. With micros, you need 70%+ win rate or tighter scalps.
5. Never trade GEX alone. Wait for other engines.
6. Real SPX data trumps everything. 9,800 strikes vs 82 SPY strikes.

Current Status

GEX Computer running with SPY proxy (low confidence but working). Need to add:
Vol Engine from Earnings-Volatility-Calculator
Greeks Aggregator from OptionStratLib
Order Block Detector
Real SPX data feed