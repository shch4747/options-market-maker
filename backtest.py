"""
backtest.py - Module 5 of the Options Market Maker

Backtests a delta-hedged short-option book on REAL market data -- the inventory
profile of a market maker who is net short options and harvesting the vol risk
premium.

Strategy (rolling, systematic):
  - Every `roll_days` trading days, SELL a `tenor_days` ATM call on the underlying.
  - Price/sell it at the market's IMPLIED vol, proxied by VIX on that date.
  - Credit the market-maker spread we'd capture (half-spread from the quote engine).
  - Delta-hedge DAILY along the real historical price path until expiry.
  - Charge transaction costs on every hedge trade.
  - At expiry, settle the payoff against the real terminal price.

Per-trade PnL = spread_capture + premium - hedging_cost - payoff
             = (market-making edge) + (realized-vs-implied vol premium)

Across all rolling trades -> PnL distribution -> Sharpe, win rate, max drawdown.

Requires (run locally, needs internet):
    pip install yfinance pandas numpy matplotlib
Integrates with: black_scholes.py, quote_engine.py
"""

import numpy as np
import pandas as pd
from black_scholes import black_scholes, delta
from quote_engine import generate_quote


# ----------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------
def fetch_data(ticker="SPY", start="2018-01-01", end="2024-01-01"):
    """Pull underlying closes + VIX (implied-vol proxy). Local internet needed."""
    import yfinance as yf
    px = yf.download(ticker, start=start, end=end, progress=False)["Close"]
    vix = yf.download("^VIX", start=start, end=end, progress=False)["Close"]
    df = pd.DataFrame({"S": px.squeeze(), "VIX": vix.squeeze()}).dropna()
    return df


# ----------------------------------------------------------------------
# Single-trade hedged simulation along a REAL price path
# ----------------------------------------------------------------------
def hedge_one_trade(path, implied_vol, r=0.04, tenor_days=21,
                    cost_rate=0.0005, option_type="call"):
    """
    path : array of real daily prices for the life of the trade (len = tenor_days+1)
    implied_vol : vol we SELL at (from VIX at entry), held fixed over the trade
    Returns (total_pnl, spread_capture, vol_pnl, hedge_cost).
    """
    n = len(path) - 1
    T = tenor_days / 252.0
    dt = 1.0 / 252.0

    S0 = path[0]
    K = S0                                  # ATM

    # market-maker spread we capture on the sale (from Module 3)
    q = generate_quote(S0, K, T, r, implied_vol, option_type)
    spread_capture = q.half_spread

    premium = black_scholes(S0, K, T, r, implied_vol, option_type)

    shares = 0.0
    cash = premium
    hedge_cost = 0.0

    for i in range(n):
        tau = T - i * dt
        target = delta(path[i], K, max(tau, 1e-8), r, implied_vol, option_type)
        trade = target - shares
        c = abs(trade) * path[i] * cost_rate
        cash -= trade * path[i] + c
        hedge_cost += c
        shares = target

    # settle
    ST = path[-1]
    unwind = abs(shares) * ST * cost_rate
    cash += shares * ST - unwind
    hedge_cost += unwind
    payoff = max(ST - K, 0.0) if option_type == "call" else max(K - ST, 0.0)
    cash -= payoff

    vol_pnl = cash                          # premium - hedge_cost - payoff (+resid)
    total = vol_pnl + spread_capture
    return total, spread_capture, vol_pnl, hedge_cost


# ----------------------------------------------------------------------
# Rolling backtest
# ----------------------------------------------------------------------
def run_backtest(df, r=0.04, tenor_days=21, roll_days=21,
                 cost_rate=0.0005, option_type="call"):
    """Roll through the price series selling+hedging one option per roll window."""
    S = df["S"].to_numpy()
    vix = df["VIX"].to_numpy()
    trades = []

    i = 0
    while i + tenor_days < len(S):
        path = S[i:i + tenor_days + 1]
        iv = vix[i] / 100.0                 # VIX is in vol points
        total, spread, volpnl, hcost = hedge_one_trade(
            path, iv, r, tenor_days, cost_rate, option_type)
        trades.append({"entry_idx": i, "iv": iv, "S0": path[0], "ST": path[-1],
                       "total": total, "spread": spread,
                       "vol_pnl": volpnl, "hedge_cost": hcost})
        i += roll_days

    return pd.DataFrame(trades)


def performance_stats(trades, periods_per_year=12):
    """Sharpe, win rate, drawdown on the per-trade PnL series."""
    p = trades["total"].to_numpy()
    mean, std = p.mean(), p.std()
    sharpe = (mean / std * np.sqrt(periods_per_year)) if std > 0 else float("nan")
    cum = np.cumsum(p)
    peak = np.maximum.accumulate(cum)
    max_dd = (peak - cum).max()

    print(f"trades            : {len(p)}")
    print(f"total PnL         : {p.sum():.2f}")
    print(f"mean PnL / trade  : {mean:.4f}")
    print(f"std  PnL / trade  : {std:.4f}")
    print(f"Sharpe (annual)   : {sharpe:.2f}")
    print(f"win rate          : {(p > 0).mean()*100:.1f}%")
    print(f"max drawdown      : {max_dd:.2f}")
    print(f"-- decomposition --")
    print(f"spread capture    : {trades['spread'].sum():.2f}")
    print(f"vol premium PnL   : {trades['vol_pnl'].sum():.2f}")
    print(f"hedging cost      : {trades['hedge_cost'].sum():.2f}")
    return {"sharpe": sharpe, "mean": mean, "std": std, "max_dd": max_dd}


def plot_equity(trades, fname="backtest_equity.png"):
    import matplotlib.pyplot as plt
    cum = np.cumsum(trades["total"].to_numpy())
    plt.figure(figsize=(10, 5))
    plt.plot(cum, lw=1.5)
    plt.axhline(0, color="grey", ls="--", lw=0.8)
    plt.title("Delta-Hedged Short-Vol Book - Cumulative PnL")
    plt.xlabel("trade #"); plt.ylabel("cumulative PnL")
    plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(fname, dpi=120)
    print(f"saved {fname}")


if __name__ == "__main__":
    df = fetch_data("SPY", "2018-01-01", "2024-01-01")
    print(f"loaded {len(df)} days, {df.index[0].date()} -> {df.index[-1].date()}\n")
    trades = run_backtest(df)
    performance_stats(trades)
    plot_equity(trades)
