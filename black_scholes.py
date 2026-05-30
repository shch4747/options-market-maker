import numpy as np
import math as math
from scipy.stats import norm


def black_scholes(S, K, T, r, sigma, option_type='call'):
    """
    S: current stock price
    K: strike price
    T: time to expiry in years
    r: risk-free interest rate (annual, decimal)
    sigma: volatility (annual, decimal)
    option_type: 'call' or 'put'
    """
    N = norm.cdf
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if option_type == 'call':
        price = S*N(d1) - N(d2)*K*np.exp(-r*T)
    elif option_type == 'put':
        price = N(-d2)*K*np.exp(-r*T) - S*N(-d1)
    
    return price

def delta(S, K, T, r, sigma, option_type='call'):
    d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    if option_type == 'call':
        return norm.cdf(d1)
    elif option_type == 'put':
        return norm.cdf(d1) - 1

def gamma(S, K, T, r, sigma):
    d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    return norm.pdf(d1) / (S * sigma * np.sqrt(T))

def theta(S, K, T, r, sigma, option_type='call'):
    d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)
    if option_type == 'call':
        return (-(S * norm.pdf(d1) * sigma) / (2*np.sqrt(T)) 
                - r * K * np.exp(-r*T) * norm.cdf(d2)) / 365
    elif option_type == 'put':
        return (-(S * norm.pdf(d1) * sigma) / (2*np.sqrt(T)) 
                + r * K * np.exp(-r*T) * norm.cdf(-d2)) / 365

def vega(S, K, T, r, sigma):
    d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    return S * norm.pdf(d1) * np.sqrt(T) / 100

def rho(S, K, T, r, sigma, option_type='call'):
    d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)
    if option_type == 'call':
        return K * T * np.exp(-r*T) * norm.cdf(d2) / 100
    elif option_type == 'put':
        return -K * T * np.exp(-r*T) * norm.cdf(-d2) / 100

def monte_carlo_call(S, K, T, r, sigma, n_simulations=10000):
    """
    Price a European call option using Monte Carlo simulation.
    """
    Z = np.random.standard_normal(n_simulations)
    ST = S * np.exp((r - 0.5 * sigma**2) * T + sigma * np.sqrt(T) * Z)
    payoffs = np.maximum(ST - K, 0)
    price = np.exp(-r * T) * np.mean(payoffs)
    return price

S, K, T, r, sigma = 100, 100, 1, 0.05, 0.2


import matplotlib.pyplot as plt

def convergence_plot(S, K, T, r, sigma):
    bs_price = black_scholes(S, K, T, r, sigma, 'call')
    simulations = [100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000]
    mc_prices = [monte_carlo_call(S, K, T, r, sigma, n) for n in simulations]
    
    plt.figure(figsize=(10, 5))
    plt.semilogx(simulations, mc_prices, 'bo-', label='MC Price')
    plt.axhline(y=bs_price, color='r', linestyle='--', label=f'BS Price: {bs_price:.4f}')
    plt.xlabel('Number of Simulations')
    plt.ylabel('Option Price')
    plt.title('Monte Carlo Convergence to Black-Scholes Price')
    plt.legend()
    plt.grid(True)
    plt.savefig('convergence.png')
    plt.show()

convergence_plot(S, K, T, r, sigma)