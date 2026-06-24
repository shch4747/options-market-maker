"""
vol_smile.py - Module 7 of the Options Market Maker (the cherry on top)

Pulls a live options chain, inverts each strike's market mid-price into an
implied volatility using the Module 2 solver, and plots the volatility smile /
skew. Then it demonstrates the concrete failure of the flat-vol Black-Scholes
assumption: price every strike with a single ATM vol and measure the mispricing
against the market.

The point: BS assumes ONE volatility for all strikes (a flat line). Real markets
price a SKEW -- OTM puts carry higher implied vol than OTM calls (crash fear).
That curve is exactly where a flat-vol model misprices, and this module
quantifies it in dollars.

We use the liquid OTM wing of each side (puts below spot, calls above) because
those are the cleanest, tightest-quoted options to invert.

Integrates with: black_scholes.py, implied_vol.py  (the Module 2 solver)
Data: yfinance (run locally, needs internet).
"""

import numpy as np
import pandas as pd
from datetime import datetime
from black_scholes import black_scholes
from implied_vol import implied_vol


def fetch_chain(ticker="SPY", target_dte=30, r=0.04):
    """
    Pull the options chain for the expiry closest to `target_dte` days out.
    Returns (spot, T_years, DataFrame[strike, type, mid]).
    """
    import yfinance as yf
    tk = yf.Ticker(ticker)
    spot = float(tk.fast_info["last_price"])

    today = datetime.now().date()
    expiries = tk.options
    # pick expiry closest to target days-to-expiry
    dtes = {e: abs((datetime.strptime(e, "%Y-%m-%d").date() - today).days - target_dte)
            for e in expiries}
    expiry = min(dtes, key=dtes.get)
    dte = (datetime.strptime(expiry, "%Y-%m-%d").date() - today).days
    T = max(dte, 1) / 365.0

    chain = tk.option_chain(expiry)

    def get_mid(row):
        """Live mid from bid/ask; fall back to lastPrice when the market is
        closed (bid/ask come back as 0/NaN outside US trading hours)."""
        bid, ask = row.bid, row.ask
        if pd.notna(bid) and pd.notna(ask) and bid > 0 and ask > 0:
            return 0.5 * (bid + ask)
        last = getattr(row, "lastPrice", float("nan"))
        if pd.notna(last) and last > 0:
            return float(last)
        return float("nan")

    rows = []
    for _, row in chain.puts.iterrows():      # OTM puts (strike <= spot)
        if row.strike <= spot:
            m = get_mid(row)
            if m == m:                        # not NaN
                rows.append({"strike": row.strike, "type": "put", "mid": m})
    for _, row in chain.calls.iterrows():     # OTM calls (strike > spot)
        if row.strike > spot:
            m = get_mid(row)
            if m == m:
                rows.append({"strike": row.strike, "type": "call", "mid": m})

    if not rows:
        raise RuntimeError(
            "No usable option quotes (bid/ask and lastPrice all empty). "
            "Yahoo sometimes returns nothing outside US market hours -- "
            "try again, or pick a different expiry/ticker.")

    df = pd.DataFrame(rows).sort_values("strike").reset_index(drop=True)
    src = "bid/ask mid" if (chain.puts["bid"] > 0).any() else "lastPrice (market closed)"
    print(f"{ticker}: spot={spot:.2f}  expiry={expiry} ({dte}d, T={T:.4f})  "
          f"strikes={len(df)}  price_source={src}")
    return spot, T, df


def build_smile(spot, T, df, r=0.04):
    """Invert each strike's mid price into an implied vol via the M2 solver."""
    ivs = []
    for _, row in df.iterrows():
        try:
            iv = implied_vol(row["mid"], spot, row["strike"], T, r, row["type"])
        except Exception:
            iv = np.nan
        ivs.append(iv)
    out = df.copy()
    out["iv"] = ivs
    out["moneyness"] = out["strike"] / spot
    # keep sane inversions only
    out = out[(out["iv"] > 0.01) & (out["iv"] < 3.0)].reset_index(drop=True)
    return out


def flat_vol_mispricing(spot, T, smile, r=0.04):
    """
    Price every strike with a single ATM flat vol and compare to market mid.
    Quantifies how badly the flat-vol BS assumption misprices the wings.
    """
    # ATM vol = iv of the strike nearest spot
    atm_idx = (smile["moneyness"] - 1.0).abs().idxmin()
    atm_vol = smile.loc[atm_idx, "iv"]

    errs = []
    for _, row in smile.iterrows():
        flat = black_scholes(spot, row["strike"], T, r, atm_vol, row["type"])
        errs.append(flat - row["mid"])
    smile = smile.copy()
    smile["flat_price"] = [black_scholes(spot, k, T, r, atm_vol, t)
                           for k, t in zip(smile["strike"], smile["type"])]
    smile["mispricing"] = smile["flat_price"] - smile["mid"]
    smile["mispricing_pct"] = smile["mispricing"] / smile["mid"] * 100
    return atm_vol, smile


def report(spot, smile, atm_vol):
    # skew summary: vol at ~90% and ~110% moneyness vs ATM
    def vol_at(m):
        i = (smile["moneyness"] - m).abs().idxmin()
        return smile.loc[i, "iv"], smile.loc[i, "moneyness"]
    v90, m90 = vol_at(0.90)
    v110, m110 = vol_at(1.10)
    print(f"\nATM implied vol         : {atm_vol*100:.1f}%")
    print(f"~90% moneyness vol      : {v90*100:.1f}%  (m={m90:.3f})  <- OTM put wing")
    print(f"~110% moneyness vol     : {v110*100:.1f}% (m={m110:.3f})  <- OTM call wing")
    print(f"put-call skew (v90-v110): {(v90 - v110)*100:+.1f} vol pts  "
          f"<- positive = downside fear")
    worst = smile.loc[smile["mispricing"].abs().idxmax()]
    print(f"\nFlat-vol BS worst mispricing: ${worst['mispricing']:+.2f} "
          f"({worst['mispricing_pct']:+.0f}%) at strike {worst['strike']:.0f} "
          f"({worst['type']})")
    print("  -> using one flat vol for all strikes misprices the wings; this is")
    print("     exactly the model error the smile reveals.")


def plot_smile(spot, smile, atm_vol, fname="vol_smile.png"):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(13, 5))

    ax[0].plot(smile["moneyness"], smile["iv"] * 100, "o-", ms=4)
    ax[0].axhline(atm_vol * 100, color="r", ls="--", lw=1.2,
                  label=f"flat ATM vol ({atm_vol*100:.1f}%) -- what BS assumes")
    ax[0].axvline(1.0, color="grey", ls=":", lw=0.8)
    ax[0].set_xlabel("moneyness  K / S")
    ax[0].set_ylabel("implied volatility (%)")
    ax[0].set_title("Volatility smile/skew from live market mids")
    ax[0].legend(); ax[0].grid(alpha=0.3)

    ax[1].bar(smile["moneyness"], smile["mispricing"],
              width=0.01, color=np.where(smile["mispricing"] >= 0, "tab:red", "tab:blue"))
    ax[1].axhline(0, color="grey", lw=0.8)
    ax[1].axvline(1.0, color="grey", ls=":", lw=0.8)
    ax[1].set_xlabel("moneyness  K / S")
    ax[1].set_ylabel("flat-vol price  -  market mid ($)")
    ax[1].set_title("Mispricing from assuming one flat vol")
    ax[1].grid(alpha=0.3)

    plt.tight_layout(); plt.savefig(fname, dpi=120)
    print(f"\nsaved {fname}")


if __name__ == "__main__":
    spot, T, df = fetch_chain("SPY", target_dte=30)
    smile = build_smile(spot, T, df)
    atm_vol, smile = flat_vol_mispricing(spot, T, smile)
    report(spot, smile, atm_vol)
    plot_smile(spot, smile, atm_vol)
