"""Recompute frozen-rule research results under explicit execution scenarios.

Run from the repository root: python scripts/validate_research.py
Historical splits do not establish that model selection was out of sample.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
import copy
import numpy as np
import pandas as pd
from config import Config
from data.loader import load_csv, build_daily_bars
from strategy.multi import MultiModelGenerator
from backtest.engine_v2 import BacktestEngineV2
from backtest.funded_sim import trades_to_daily_pnl, run_monte_carlo, run_eval_monte_carlo
from scripts.research_rows import accelerate_research


def summarize(trades):
    r = np.array([t.total_r for t in trades])
    equity = np.r_[0, r.cumsum()]
    return {'trades': len(r), 'win_rate': float((r > 0).mean()) if len(r) else 0,
            'expectancy_r': float(r.mean()) if len(r) else 0,
            'total_r': float(r.sum()),
            'profit_factor': float(r[r > 0].sum() / -r[r < 0].sum()) if (r < 0).any() else None,
            'max_drawdown_r': float((equity - np.maximum.accumulate(equity)).min())}


def main():
    out = Path('output/validation'); out.mkdir(parents=True, exist_ok=True)
    raw = pd.concat([load_csv('data/Dataset_NQ_1min_2022_2025.csv'),
                     load_csv('data/mnq_2026_1min.csv')], ignore_index=True)
    raw = raw.sort_values('datetime').drop_duplicates('datetime').reset_index(drop=True)
    daily = build_daily_bars(raw)
    daily['date'] = pd.to_datetime(daily['date']).dt.date
    cfg = Config()
    print(f'Generating frozen signals for {len(raw):,} bars', flush=True)
    signals = accelerate_research(MultiModelGenerator(cfg)).generate(raw, daily)
    dates = daily['date'].tolist()
    results = {'bars': len(raw), 'signals': len(signals),
               'start': str(raw.datetime.min()), 'end': str(raw.datetime.max()),
               'method': 'Frozen rules, chronological year slices; no claim of independent model selection',
               'monte_carlo': '25000 five-day-block bootstrap draws; end-of-day account mechanics',
               'scenarios': {}}
    for name, slip, fee in [('conservative_no_cost', 0, 0),
                             ('base', 1, 0.62), ('stress', 2, 1.24)]:
        scenario = copy.deepcopy(cfg)
        scenario.risk.entry_slippage_ticks = scenario.risk.exit_slippage_ticks = slip
        scenario.risk.commission_per_side = fee
        print(f'Simulating {name}', flush=True)
        trades = BacktestEngineV2(scenario).run(raw, signals)
        pnl = trades_to_daily_pnl(trades, dates, scenario)
        result = summarize(trades)
        result['costs'] = {'entry_slippage_ticks': slip, 'exit_slippage_ticks': slip,
                           'commission_per_side_usd': fee}
        result['year_slices'] = {str(y): summarize([t for t in trades if t.entry_time.year == y])
                                  for y in sorted({t.entry_time.year for t in trades})}
        # Monte Carlo uses only the latest file's year as a separate sensitivity slice.
        held_out_year = load_csv('data/mnq_2026_1min.csv').datetime.min().year
        forward_pnl = pnl[np.array([d.year == held_out_year for d in dates])]
        result['latest_year_eval_mc'] = run_eval_monte_carlo(forward_pnl, scenario)
        result['latest_year_funded_mc'] = run_monte_carlo(forward_pnl, scenario)
        result['daily_cap_overruns'] = int((pnl < -scenario.funded.dollar_loss_cap).sum())
        pd.DataFrame([{'entry_time': t.entry_time, 'exit_time': t.exit_time,
                       'model': t.model, 'direction': t.direction, 'total_r': t.total_r,
                       'commission_r': t.commission_r, 'risk_ticks': t.risk_ticks,
                       'exit_reason': t.exit_reason} for t in trades]).to_csv(out / f'{name}_trades.csv', index=False)
        results['scenarios'][name] = result
        (out / 'research_results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
