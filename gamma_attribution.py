"""
gamma_attribution.py - Module 6 of the Options Market Maker (finale)

Cracks open the hedged P&L day-by-day and attributes it to the two Greeks that
actually drive a delta-hedged option book:

    daily P&L (short option, delta-hedged)  ~=  theta_pnl  +  gamma_pnl
    where   theta_pnl = +(daily time decay we collect, since we're short)
            gamma_pnl = -0.5 * Gamma * (dS)^2   (we PAY on big moves)

We compute each daily P&L EXACTLY by revaluation, split it into an exact theta
piece (reprice holding S fixed, step time forward) and a spot piece (reprice
holding time fixed, move S), then compare the spot piece against the gamma
approximation -0.5*Gamma*dS^2. Plotting daily P&L vs (dS)^2 yields the signature
downward line of a short-gamma book.

Integrates with: black_scholes.py (black_scholes, delta, gamma)
Data: reuses backtest.fetch_data when run locally; falls back to synthetic.
"""

import numpy as np
import pandas as pd
from black_scholes import black_scholes, delta, gamma


def attribute_path(path, implied_vol, r=0.04, tenor_days=21, option_type="call"):
    """
    Walk one option's life along a real price path, returning a per-day
    attribution record. Position: SHORT 1 option, delta-hedged each day.
    """
    n = len(path) - 1
    T = tenor_days / 252.0
    dt = 1.0 / 252.0
    K = path[0]                              # ATM at entry
    recs = []

    for i in range(n):
        tau_now = T - i * dt
        tau_next = T - (i + 1) * dt
        if tau_now <= 1e-8:
            break

        S_i, S_next = path[i], path[i + 1]
        dS = S_next - S_i

        V_now = black_scholes(S_i, K, tau_now, r, implied_vol, option_type)
        V_time = black_scholes(S_i, K, max(tau_next, 1e-8), r, implied_vol, option_type)
        V_next = black_scholes(S_next, K, max(tau_next, 1e-8), r, implied_vol, option_type)

        # EXACT split of the option's value change (we are SHORT -> negate)
        theta_pnl = -(V_time - V_now)                    # collect decay (>0 typ.)
        spot_pnl = -(V_next - V_time)                    # option's spot move (short)
        d = delta(S_i, K, tau_now, r, implied_vol, option_type)
        hedge_pnl = d * dS                               # long d shares
        deltahedged_spot = spot_pnl + hedge_pnl          # ~ -0.5*Gamma*dS^2

        # gamma APPROXIMATION to the delta-hedged spot piece
        g = gamma(S_i, K, tau_now, r, implied_vol)
        gamma_pnl_pred = -0.5 * g * dS**2

        actual_daily = theta_pnl + deltahedged_spot      # exact daily hedged P&L

        recs.append({
            "S": S_i, "dS": dS, "dS2": dS**2,
            "theta_pnl": theta_pnl,
            "gamma_pnl_exact": deltahedged_spot,
            "gamma_pnl_pred": gamma_pnl_pred,
            "actual_daily": actual_daily,
        })
    return pd.DataFrame(recs)


def run_attribution(df, r=0.04, tenor_days=21, roll_days=21, option_type="call"):
    """Aggregate daily attribution across every rolling trade in the backtest."""
    S = df["S"].to_numpy()
    vix = df["VIX"].to_numpy()
    all_recs = []
    i = 0
    while i + tenor_days < len(S):
        path = S[i:i + tenor_days + 1]
        iv = vix[i] / 100.0
        rec = attribute_path(path, iv, r, tenor_days, option_type)
        all_recs.append(rec)
        i += roll_days
    return pd.concat(all_recs, ignore_index=True)


def summarize(att):
    theta_tot = att["theta_pnl"].sum()
    gamma_tot = att["gamma_pnl_exact"].sum()
    # how well does the gamma approximation explain the delta-hedged spot P&L?
    corr = np.corrcoef(att["gamma_pnl_exact"], att["gamma_pnl_pred"])[0, 1]
    print(f"days attributed      : {len(att)}")
    print(f"theta collected (sum): {theta_tot:.2f}   <- what we earn for being short")
    print(f"gamma paid (sum)     : {gamma_tot:.2f}   <- what big moves cost us")
    print(f"net (theta + gamma)  : {theta_tot + gamma_tot:.2f}   <- ~ the vol premium")
    print(f"corr(exact, -0.5 G dS^2): {corr:.4f}   <- gamma approx quality")
    # the signature: slope of daily P&L vs dS^2 should be negative (short gamma)
    slope = np.polyfit(att["dS2"], att["actual_daily"], 1)[0]
    print(f"slope d(PnL)/d(dS^2) : {slope:.5f}   <- negative => short gamma")


def plot_signature(att, fname="gamma_signature.png"):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(13, 5))

    # (1) the signature scatter: daily P&L vs squared move
    ax[0].scatter(att["dS2"], att["actual_daily"], s=8, alpha=0.35)
    xs = np.linspace(0, att["dS2"].max(), 100)
    m, b = np.polyfit(att["dS2"], att["actual_daily"], 1)
    ax[0].plot(xs, m * xs + b, "r-", lw=2, label=f"fit slope={m:.4f}")
    ax[0].axhline(0, color="grey", ls="--", lw=0.8)
    ax[0].set_xlabel("squared daily move  (dS)^2")
    ax[0].set_ylabel("daily hedged P&L")
    ax[0].set_title("Short-gamma signature: P&L falls as moves grow")
    ax[0].legend(); ax[0].grid(alpha=0.3)

    # (2) cumulative theta vs cumulative gamma over the whole history
    ax[1].plot(np.cumsum(att["theta_pnl"]), label="cumulative theta (collected)")
    ax[1].plot(np.cumsum(att["gamma_pnl_exact"]), label="cumulative gamma (paid)")
    ax[1].plot(np.cumsum(att["actual_daily"]), label="net", lw=2, color="k")
    ax[1].axhline(0, color="grey", ls="--", lw=0.8)
    ax[1].set_xlabel("day"); ax[1].set_ylabel("cumulative P&L")
    ax[1].set_title("Theta income vs gamma cost over time")
    ax[1].legend(); ax[1].grid(alpha=0.3)

    plt.tight_layout(); plt.savefig(fname, dpi=120)
    print(f"saved {fname}")


if __name__ == "__main__":
    try:
        from backtest import fetch_data
        df = fetch_data("SPY", "2018-01-01", "2024-01-01")
        print(f"REAL data: {len(df)} days "
              f"{df.index[0].date()} -> {df.index[-1].date()}\n")
    except Exception as e:
        print(f"[no internet/yfinance -> synthetic demo] ({type(e).__name__})\n")
        rng = np.random.default_rng(7)
        n = 252 * 6
        rv = 0.16
        rets = (0.06 - 0.5*rv**2)/252 + rv*np.sqrt(1/252)*rng.standard_normal(n)
        S = 250*np.exp(np.cumsum(rets))
        vix = np.clip(18 + 3*np.sin(np.linspace(0, 12, n)) + rng.standard_normal(n)*2, 9, 60)
        df = pd.DataFrame({"S": S, "VIX": vix})

    att = run_attribution(df)
    summarize(att)
    plot_signature(att)
