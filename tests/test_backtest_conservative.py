"""Regression scenarios for execution assumptions and dollar loss overruns."""
from types import SimpleNamespace
import pandas as pd
import pytest
from config import Config
from strategy.models.base import Signal, ModelRiskProfile
from backtest.engine_v2 import BacktestEngineV2
from backtest.funded_sim import trades_to_daily_pnl


def simulate(bars, direction='long', costs=False, **profile):
    cfg = Config()
    if not costs:
        cfg.risk.entry_slippage_ticks = cfg.risk.exit_slippage_ticks = 0
        cfg.risk.commission_per_side = 0
    start = pd.Timestamp('2026-03-02 10:00')
    df = pd.DataFrame([(100, 100, 100, 100)] + bars,
                      columns=['open', 'high', 'low', 'close'])
    df['datetime'] = pd.date_range(start, periods=len(df), freq='min')
    stop, target = (90, 120) if direction == 'long' else (110, 80)
    rp = ModelRiskProfile(min_rr=0.1, be_trigger_rr=100, partial_rr=100,
                          partial_pct=0, **profile)
    sig = Signal(0, start, 'test', direction, 100, stop, target, 40, 80, 2,
                 risk_profile=rp)
    return BacktestEngineV2(cfg)._sim(df, sig)


@pytest.mark.parametrize('direction,bars', [
    ('long', [(110, 125, 89, 100)]),
    ('short', [(90, 111, 75, 100)]),
])
def test_ambiguous_bar_always_takes_stop(direction, bars):
    t = simulate(bars, direction)
    assert t.exit_reason == 'stop_ambiguous'
    assert t.total_r == pytest.approx(-1)


def test_trail_change_does_not_use_current_bar_low():
    # First bar activates the trail. Second bar raises it, but its low cannot
    # hit that new level retroactively. Third bar opens through the raised stop.
    cfg = Config()
    cfg.risk.entry_slippage_ticks = cfg.risk.exit_slippage_ticks = 0
    cfg.risk.commission_per_side = 0
    start = pd.Timestamp('2026-03-02 10:00')
    df = pd.DataFrame([(100, 100, 100, 100), (100, 111, 99, 110),
                       (110, 120, 108, 119), (114, 114, 113, 114)],
                      columns=['open', 'high', 'low', 'close'])
    df['datetime'] = pd.date_range(start, periods=4, freq='min')
    rp = ModelRiskProfile(min_rr=0.1, partial_rr=1, partial_pct=0.5,
                          be_trigger_rr=100, trail_pct=0.5)
    sig = Signal(0, start, 'test', 'long', 100, 90, 140, 40, 160, 4,
                 risk_profile=rp)
    t = BacktestEngineV2(cfg)._sim(df, sig)
    assert t.exit_time == df.iloc[3]['datetime']
    assert t.exit_price == 114  # gap below stop at 115


def test_gap_stop_fills_at_open():
    t = simulate([(100, 101, 99, 100), (85, 87, 84, 86)])
    assert t.exit_price == 85
    assert t.total_r == -1.5


def test_costs_reduce_net_returns():
    free = simulate([(100, 121, 99, 120)])
    paid = simulate([(100, 121, 99, 120)], costs=True)
    assert paid.entry_price == 100.25
    assert paid.commission_r > 0
    assert paid.total_r < free.total_r
    assert paid.total_r == pytest.approx(19.75 / 10.25 - 1.24 / 20.5)


def test_target_on_wrong_side_is_rejected():
    assert simulate([(125, 126, 124, 125)]) is None


def test_dollar_cap_preserves_overrun_and_blocks_next_trade():
    cfg = Config()
    d = pd.Timestamp('2026-03-02 10:00')
    ts = [SimpleNamespace(entry_time=d, risk_ticks=40, model='ou_rev', total_r=r)
          for r in [-3, 10]]
    assert trades_to_daily_pnl(ts, [d.date()], cfg).tolist() == [-1200]


def test_session_close_prevents_late_fill():
    cfg = Config()
    start = pd.Timestamp('2026-03-02 15:54')
    df = pd.DataFrame({'datetime': [start, start + pd.Timedelta(minutes=1)],
                       'open': [100, 100], 'high': [100, 101],
                       'low': [100, 99], 'close': [100, 100]})
    sig = Signal(0, start, 'test', 'long', 100, 90, 120, 40, 80, 2)
    assert BacktestEngineV2(cfg)._sim(df, sig) is None


def test_configured_contract_cap_controls_funded_sizing():
    cfg = Config(); cfg.risk.max_contracts = 2
    d = pd.Timestamp('2026-03-02 10:00')
    t = SimpleNamespace(entry_time=d, risk_ticks=40, model='ou_rev', total_r=1)
    assert trades_to_daily_pnl([t], [d.date()], cfg).tolist() == [40]


def test_short_gap_stop_fills_at_open():
    t = simulate([(100, 101, 99, 100), (115, 116, 114, 115)], 'short')
    assert t.exit_price == 115
    assert t.total_r == -1.5


def test_commissions_apply_to_losing_trade():
    t = simulate([(100, 101, 89, 90)], costs=True)
    assert t.exit_price == 89.75
    assert t.total_r == pytest.approx(-10.5 / 10.25 - 1.24 / 20.5)
