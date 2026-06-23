"""
quote_engine.py — Module 3 of the Options Market Maker

Turns a theoretical value into an actual two-sided market: a bid (we buy here)
and an ask (we sell here), with the spread scaled by risk.

Core market-maker logic:
  - We never trade AT theo. We quote bid = theo - half_spread, ask = theo + half_spread.
    The spread is our compensation for providing liquidity and warehousing risk.
  - The spread WIDENS with risk. Two drivers:
       * volatility (sigma): higher vol => value is more uncertain / can move
         against us faster => demand a wider spread.
       * vega exposure: the more sensitive the option is to a vol move (vega
         peaks near-the-money), the more an unexpected vol shock hurts => widen.

  half_spread = base + k_vol * sigma + k_vega * vega_display

We report the quote in DOLLARS (what we actually post) and the spread in BPS
(relative to theo), so spreads are comparable across cheap and expensive options
and feed cleanly into the backtest's revenue accounting later.

Integrates with black_scholes.py:
    black_scholes(S, K, T, r, sigma, option_type)
    vega(S, K, T, r, sigma)   -> vega per 1% vol move (the 'display' vega)
"""

from dataclasses import dataclass
from black_scholes import black_scholes, vega


@dataclass
class Quote:
    theo: float          # theoretical (fair) value from the pricer
    bid: float           # price we buy at  (theo - half_spread)
    ask: float           # price we sell at (theo + half_spread)
    half_spread: float   # dollars on each side of theo
    spread: float        # full ask - bid, in dollars
    spread_bps: float    # full spread relative to theo, in basis points

    def __repr__(self):
        return (f"Quote(theo={self.theo:.4f}, bid={self.bid:.4f}, "
                f"ask={self.ask:.4f}, spread=${self.spread:.4f} "
                f"[{self.spread_bps:.0f} bps])")


def generate_quote(S, K, T, r, sigma, option_type='call',
                   base=0.05, k_vol=0.50, k_vega=0.20):
    """
    Build a two-sided quote around theoretical value.

    base   : minimum half-spread floor in dollars (we never quote tighter)
    k_vol  : how aggressively the spread widens with volatility
    k_vega : how aggressively the spread widens with vega exposure

    Returns a Quote.
    """
    theo = black_scholes(S, K, T, r, sigma, option_type)
    v = vega(S, K, T, r, sigma)          # per-1% vol move (display vega)

    half_spread = base + k_vol * sigma + k_vega * v

    bid = max(0.0, theo - half_spread)   # an option price can't go negative
    ask = theo + half_spread
    spread = ask - bid

    # bps relative to theo; guard against the deep-OTM theo~0 blow-up
    spread_bps = (spread / theo * 10_000) if theo > 1e-6 else float('inf')

    return Quote(theo=theo, bid=bid, ask=ask,
                 half_spread=half_spread, spread=spread, spread_bps=spread_bps)


if __name__ == "__main__":
    S, T, r, sigma = 100.0, 1.0, 0.05, 0.20

    print("Quotes across strikes (S=100, T=1, r=5%, sigma=20%):")
    print(f"{'K':>6} | {'theo':>8} | {'bid':>8} | {'ask':>8} | "
          f"{'spread$':>8} | {'bps':>7} | {'vega':>6}")
    print("-" * 66)
    for K in [80, 90, 100, 110, 120]:
        q = generate_quote(S, K, T, r, sigma, 'call')
        v = vega(S, K, T, r, sigma)
        print(f"{K:>6} | {q.theo:>8.4f} | {q.bid:>8.4f} | {q.ask:>8.4f} | "
              f"{q.spread:>8.4f} | {q.spread_bps:>7.0f} | {v:>6.3f}")

    print("\nSame ATM option, spread widening as volatility rises:")
    print(f"{'sigma':>6} | {'theo':>8} | {'spread$':>8} | {'bps':>7}")
    print("-" * 36)
    for sig in [0.10, 0.20, 0.40, 0.80]:
        q = generate_quote(100, 100, T, r, sig, 'call')
        print(f"{sig:>6.2f} | {q.theo:>8.4f} | {q.spread:>8.4f} | {q.spread_bps:>7.0f}")
