from black_scholes import black_scholes, vega


def _dprice_dsigma(S, K, T, r, sigma):
    """True analytic derivative dPrice/dSigma. Your vega() is this / 100, so
    multiply back to get the value Newton-Raphson actually needs."""
    return vega(S, K, T, r, sigma) * 100.0


# ----------------------------------------------------------------------
# Newton-Raphson solver
# ----------------------------------------------------------------------
def implied_vol_newton(market_price, S, K, T, r, option_type='call',
                       sigma_init=0.20, tol=1e-6, max_iter=100):
    """
    Solve f(sigma) = black_scholes(sigma) - market_price = 0.
    Newton update: sigma_new = sigma - f(sigma) / f'(sigma),
    where f'(sigma) = dPrice/dSigma (the true vega).
    Raises RuntimeError if it can't make progress -> caller falls back.
    """
    sigma = sigma_init
    for _ in range(max_iter):
        price = black_scholes(S, K, T, r, sigma, option_type)
        diff = price - market_price            # f(sigma)
        if abs(diff) < tol:
            return sigma

        deriv = _dprice_dsigma(S, K, T, r, sigma)
        if deriv < 1e-8:
            raise RuntimeError("vega too small for Newton-Raphson")

        sigma = sigma - diff / deriv
        if sigma <= 0:
            raise RuntimeError("Newton stepped into non-positive vol")

    raise RuntimeError("Newton-Raphson did not converge")


# ----------------------------------------------------------------------
# Bisection fallback
# ----------------------------------------------------------------------
def implied_vol_bisection(market_price, S, K, T, r, option_type='call',
                          low=1e-4, high=5.0, tol=1e-6, max_iter=200):
    """
    black_scholes is monotonically increasing in sigma, so bisection on
    [low, high] always keeps the root bracketed. Slow but cannot diverge.
    """
    for _ in range(max_iter):
        mid = 0.5 * (low + high)
        price = black_scholes(S, K, T, r, mid, option_type)
        diff = price - market_price

        if abs(diff) < tol:
            return mid
        if diff > 0:
            high = mid      # model too expensive -> vol too high -> search lower
        else:
            low = mid       # model too cheap    -> vol too low  -> search higher

    return 0.5 * (low + high)


# ----------------------------------------------------------------------
# Hybrid: try Newton, fall back to bisection
# ----------------------------------------------------------------------
def implied_vol(market_price, S, K, T, r, option_type='call'):
    """The function the rest of the system should call. Fast Newton, robust
    bisection fallback, so it always returns an answer."""
    try:
        return implied_vol_newton(market_price, S, K, T, r, option_type)
    except RuntimeError:
        return implied_vol_bisection(market_price, S, K, T, r, option_type)


# ----------------------------------------------------------------------
# Self-test: round-trip a known vol through the pricer and back
# ----------------------------------------------------------------------
if __name__ == "__main__":
    S, K, T, r = 100.0, 100.0, 1.0, 0.05

    print("Round-trip test (recover a known sigma from its BS price):")
    print(f"{'true_sigma':>10} | {'price':>8} | {'recovered':>10} | {'abs_err':>9}")
    print("-" * 48)

    for true_sigma in [0.10, 0.20, 0.35, 0.50, 0.80]:
        price = black_scholes(S, K, T, r, true_sigma, 'call')
        recovered = implied_vol(price, S, K, T, r, 'call')
        err = abs(recovered - true_sigma)
        print(f"{true_sigma:>10.4f} | {price:>8.4f} | {recovered:>10.6f} | {err:>9.2e}")

    print("\nDeep OTM stress test (forces the bisection fallback):")
    K_otm = 160.0
    true_sigma = 0.25
    price = black_scholes(S, K_otm, T, r, true_sigma, 'call')
    recovered = implied_vol(price, S, K_otm, T, r, 'call')
    print(f"  true={true_sigma:.4f}  price={price:.6f}  recovered={recovered:.6f}  "
          f"abs_err={abs(recovered - true_sigma):.2e}")
