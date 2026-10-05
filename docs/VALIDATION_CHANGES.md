# Conservative research validation fork

Upstream: s-k-28/nq-es-trader-5k-payout,
snapshot 0ee4392d4e11b1ab9a110cc05122f70c3b8af667.
Original MIT license and attribution are preserved.

## Changes

- Realized dollar losses are retained even when they overrun the daily cap;
  subsequent trades stop after the cap is reached. Sizing reads configured
  MNQ tick value and contract cap.
- Stop/target collisions assume stop first. Stop gaps fill at the worse open.
  Trailing and breakeven updates derived from a bar apply on the following bar.
  This is a conservative OHLC approximation, not tick-level reconstruction.
- Entry slippage, market-exit slippage and round-trip per-contract commissions
  are configurable. Base assumptions: one tick each side for market fills,
  USD 0.62 per side. Stress: two ticks and USD 1.24 per side. These are research
  inputs, not a verified broker fee schedule. Limit target fills have no assumed
  slippage; queue position and partial liquidity remain unmodeled.
- Fill entries at/after 15:55 ET and entries crossing a calendar day are rejected.
  The backtest session-close setting now agrees with the advertised 15:55 ET.
- History supplied to run_multi is warmup only and cannot inflate the evaluated
  period with historical trades.
- Forward GO requires at least 100 trades and 30 distinct trading days, valid
  finite trade records with timezone-aware timestamps, per-account loss-cap
  compliance, and a 95% five-day-block bootstrap expectancy lower bound above
  half the configured baseline. Accounts are clustered by day for uncertainty.
  The command exits with status 2 unless GO; missing evidence fails closed.
  These thresholds are screening choices, not a universal statistical guarantee.

## Reproduction

```
python -m pip install -r requirements-tested.txt
python -m pytest tests -q
python scripts/validate_research.py
```

The research script recomputes all included one-minute data under three scenarios
and saves net trades and per-year slices to output/validation. Latest-year daily
results feed 25,000 seeded evaluation and funded Monte Carlo draws.
Research runs use a read-only scalar-row adapter to avoid creating temporary
pandas Series for every model and minute. Regression checks compare its combined
signals against the pandas path across a sample spanning the included years;
normal backtest and live signal generation retain the original pandas path.

## Limits

The upstream README, charts, cached CSVs and tier performance constants contain
historical upstream claims. They are not validated fork results; only fresh
output/validation artifacts refer to the modified assumptions. Year slices use
frozen strategy rules. The repository does not establish when model selection
or tuning occurred, so these slices are not proof of independently held-out
performance. Daily Monte Carlo does not reconstruct intraday peak drawdown,
execution outages or liquidity. The daily dollar filter operates on an existing
trade stream, so it does not regenerate alternative signals after skipped trades.
Actual costs, prop-firm rules, live execution parity and forward performance
need separate verification. No live broker connection or real order is required
or used for these tests.
