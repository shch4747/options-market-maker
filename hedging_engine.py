import numpy as np
from black_scholes import black_scholes, delta


def simulate_hedge(S0, K, T, r, implied_vol, realized_vol,
                   n_steps=252, hedge_every=1, cost_rate=0.0005,
                   option_type='call', rng=None):
    """
    Simulate one hedged path. Returns a dict of P&L components.

    hedge_every : re-hedge every k steps (1 = every step/continuous,
                  larger = less frequent hedging)
    cost_rate   : transaction cost as a fraction of traded notional
                  (0.0005 = 5 bps per dollar of stock traded)
    """
    if rng is None:
        rng = np.random.default_rng()

    dt = T / n_steps

    # --- 1. Simulate the GBM stock path at REALIZED vol ---
    Z = rng.standard_normal(n_steps)
    log_returns = (r - 0.5 * realized_vol**2) * dt + realized_vol * np.sqrt(dt) * Z
    S = np.empty(n_steps + 1)
    S[0] = S0
    S[1:] = S0 * np.exp(np.cumsum(log_returns))

    # --- 2. Sell one call, collect premium (priced at IMPLIED vol) ---
    premium = black_scholes(S0, K, T, r, implied_vol, option_type)

    # --- 3. Walk the path, re-hedging every `hedge_every` steps ---
    shares = 0.0           # current stock holding
    cash = premium         # start with the premium collected
    total_cost = 0.0       # accumulated transaction costs

    for i in range(n_steps + 1):
        tau = T - i * dt   # time remaining to expiry

        # Re-hedge on schedule, but never on the final step (handled at settle)
        if i % hedge_every == 0 and i < n_steps:
            if tau > 1e-8:
                target = delta(S[i], K, T - i * dt, r, implied_vol, option_type)
            else:
                target = 0.0
            trade = target - shares          # shares to buy(+)/sell(-)
            cost = abs(trade) * S[i] * cost_rate
            cash -= trade * S[i]             # pay for shares (or receive if selling)
            cash -= cost
            total_cost += cost
            shares = target

    # --- 4. Settle at expiry: unwind stock, pay option payoff ---
    ST = S[-1]
    # close the stock position (pay a cost on the unwind too)
    unwind_cost = abs(shares) * ST * cost_rate
    cash += shares * ST - unwind_cost
    total_cost += unwind_cost
    shares = 0.0

    payoff = max(ST - K, 0.0) if option_type == 'call' else max(K - ST, 0.0)
    cash -= payoff                            # we're short the option

    pnl = cash
    return {
        "pnl": pnl,
        "premium": premium,
        "payoff": payoff,
        "total_cost": total_cost,
        "ST": ST,
    }


def run_experiment(S0=100, K=100, T=30/252, r=0.05,
                   implied_vol=0.20, realized_vol=0.20,
                   n_steps=252, cost_rate=0.0005,
                   hedge_freqs=(1, 2, 5, 10, 21), n_paths=2000, seed=42):
    """
    Sweep hedge frequency. For each frequency, run many paths and report the
    mean P&L (cost drag) and std of P&L (hedging error). This is the money result.
    """
    rng = np.random.default_rng(seed)

    print(f"S0={S0}  K={K}  T={T*252:.0f}d  implied_vol={implied_vol}  "
          f"realized_vol={realized_vol}  cost={cost_rate*1e4:.0f}bps  paths={n_paths}")
    print(f"{'hedge_every':>11} | {'mean_PnL':>9} | {'std_PnL':>9} | "
          f"{'mean_cost':>9}")
    print("-" * 48)

    results = {}
    for he in hedge_freqs:
        pnls, costs = [], []
        for _ in range(n_paths):
            out = simulate_hedge(S0, K, T, r, implied_vol, realized_vol,
                                 n_steps=n_steps, hedge_every=he,
                                 cost_rate=cost_rate, rng=rng)
            pnls.append(out["pnl"])
            costs.append(out["total_cost"])
        pnls = np.array(pnls)
        results[he] = {"mean": pnls.mean(), "std": pnls.std(),
                       "mean_cost": np.mean(costs)}
        print(f"{he:>11} | {pnls.mean():>9.4f} | {pnls.std():>9.4f} | "
              f"{np.mean(costs):>9.4f}")
    return results


if __name__ == "__main__":
    print("=== Baseline: realized vol == implied vol (correctness check) ===")
    print("Expect mean PnL near zero, std GROWS as you hedge less often,")
    print("and cost SHRINKS as you hedge less often.\n")
    run_experiment(implied_vol=0.20, realized_vol=0.20)

    print("\n=== Vol arb: SELL at 25% implied, stock realizes only 15% ===")
    print("Expect POSITIVE mean PnL: we sold expensive vol, it came in cheap.\n")
    run_experiment(implied_vol=0.25, realized_vol=0.15)

    print("\n=== Adverse: SELL at 15% implied, stock realizes 25% ===")
    print("Expect NEGATIVE mean PnL: we sold cheap vol, it blew out.\n")
    run_experiment(implied_vol=0.15, realized_vol=0.25)
