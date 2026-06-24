"""
api.py - FastAPI backend for the Options Analytics Dashboard.

Wraps the options market maker engine in a clean REST API so a browser frontend
can price options, compute Greeks, generate quotes, and visualise the Greek
surfaces live. Heavier endpoints (vol smile, backtest) call yfinance and are
meant to run where there's internet access.

Run:  uvicorn api:app --reload
Docs: http://localhost:8000/docs   (auto-generated interactive API docs)
"""

import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import black_scholes as bs

app = FastAPI(title="Options Analytics API", version="1.0")

# allow the React dev server / deployed frontend to call this API
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


# ----------------------------- request models -----------------------------
class OptionParams(BaseModel):
    S: float = Field(100, description="spot price")
    K: float = Field(100, description="strike")
    T: float = Field(1.0, description="time to expiry (years)")
    r: float = Field(0.05, description="risk-free rate")
    sigma: float = Field(0.20, description="volatility")
    option_type: str = Field("call", pattern="^(call|put)$")


# ----------------------------- core endpoints -----------------------------
@app.get("/")
def health():
    return {"status": "ok", "service": "Options Analytics API"}


@app.post("/price")
def price(p: OptionParams):
    """Black-Scholes price for the given option."""
    return {"price": bs.black_scholes(p.S, p.K, p.T, p.r, p.sigma, p.option_type)}


@app.post("/greeks")
def greeks(p: OptionParams):
    """All five Greeks at the requested point."""
    return {
        "delta": bs.delta(p.S, p.K, p.T, p.r, p.sigma, p.option_type),
        "gamma": bs.gamma(p.S, p.K, p.T, p.r, p.sigma),
        "theta": bs.theta(p.S, p.K, p.T, p.r, p.sigma, p.option_type),
        "vega": bs.vega(p.S, p.K, p.T, p.r, p.sigma),
        "rho": bs.rho(p.S, p.K, p.T, p.r, p.sigma, p.option_type),
    }


@app.post("/quote")
def quote(p: OptionParams):
    """Two-sided market-maker quote: bid/ask around theo with a risk-scaled spread."""
    theo = bs.black_scholes(p.S, p.K, p.T, p.r, p.sigma, p.option_type)
    v = bs.vega(p.S, p.K, p.T, p.r, p.sigma)
    half = 0.05 + 0.50 * p.sigma + 0.20 * v
    bid = max(0.0, theo - half)
    ask = theo + half
    return {"theo": theo, "bid": bid, "ask": ask,
            "spread": ask - bid,
            "spread_bps": (ask - bid) / theo * 1e4 if theo > 1e-6 else None}


@app.post("/greek-curve")
def greek_curve(p: OptionParams, greek: str = "delta", points: int = 60):
    """
    Sweep spot across a range and return the chosen Greek at each point -- this
    is what the frontend plots as an interactive curve.
    """
    spots = np.linspace(max(1.0, p.K * 0.5), p.K * 1.5, points)
    fns = {"delta": lambda s: bs.delta(s, p.K, p.T, p.r, p.sigma, p.option_type),
           "gamma": lambda s: bs.gamma(s, p.K, p.T, p.r, p.sigma),
           "theta": lambda s: bs.theta(s, p.K, p.T, p.r, p.sigma, p.option_type),
           "vega":  lambda s: bs.vega(s, p.K, p.T, p.r, p.sigma),
           "price": lambda s: bs.black_scholes(s, p.K, p.T, p.r, p.sigma, p.option_type)}
    f = fns.get(greek, fns["delta"])
    return {"spot": spots.tolist(), "value": [f(s) for s in spots], "greek": greek}


# ----------------- data endpoints (need internet, run locally) -----------------
@app.get("/smile")
def smile(ticker: str = "SPY", target_dte: int = 30):
    """Live volatility smile from a real options chain (requires yfinance)."""
    try:
        from vol_smile import fetch_chain, build_smile, flat_vol_mispricing
        spot, T, df = fetch_chain(ticker, target_dte)
        sm = build_smile(spot, T, df)
        atm_vol, sm = flat_vol_mispricing(spot, T, sm)
        return {"spot": spot, "atm_vol": atm_vol,
                "moneyness": sm["moneyness"].tolist(),
                "iv": sm["iv"].tolist(),
                "mispricing": sm["mispricing"].tolist()}
    except Exception as e:
        return {"error": str(e),
                "hint": "needs internet + vol_smile.py; run locally during/after US market hours"}
