"""Tests for the forward-validation GO/NO-GO gate."""
from __future__ import annotations
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from validate_forward import compute_live_stats, gate


def _write_log(tmp_path, trades):
    """trades: list of (total_r, pnl_usd, date 'YYYY-MM-DD')."""
    p = tmp_path / 'decisions.jsonl'
    with open(p, 'w') as f:
        for r, pnl, d in trades:
            f.write(json.dumps({
                'action': 'trade_closed', 'total_r': r, 'pnl_usd': pnl,
                'timestamp': f'{d}T10:00:00-05:00',
            }) + '\n')
        # noise lines that must be ignored
        f.write(json.dumps({'action': 'skip_signal', 'reason': 'x'}) + '\n')
        f.write('not json\n')
    return str(p)


def _good_trades(n=400):
    # ~45% WR, ~+0.23R expectancy, one trade per distinct day (no cap breach).
    out = []
    for i in range(n):
        from datetime import date, timedelta
        d = (date(2026, 1, 1) + timedelta(days=i)).isoformat()
        if (i * 17) % 40 < 18:   # 18 wins interleaved with losses
            out.append((1.3, 130.0, d))
        else:             # 22 losses
            out.append((-0.65, -65.0, d))
    return out


def test_insufficient_data(tmp_path):
    log = _write_log(tmp_path, _good_trades(10))
    out = gate(compute_live_stats([log]))
    assert out['verdict'] == 'INSUFFICIENT_DATA'


def test_go_when_tracking_baseline(tmp_path):
    log = _write_log(tmp_path, _good_trades(400))
    stats = compute_live_stats([log])
    assert stats['n_trades'] == 400
    assert 44 <= stats['win_rate'] <= 46
    assert stats['expectancy_r'] > 0.11
    assert gate(stats)['verdict'] == 'GO'


def test_no_go_low_expectancy(tmp_path):
    # 40 trades, all small losses spread across days (no cap breach) -> NO_GO.
    trades = [(-0.2, -20.0, d) for _, _, d in _good_trades(100)]
    out = gate(compute_live_stats([_write_log(tmp_path, trades)]))
    assert out['verdict'] == 'NO_GO'
    assert any(name == 'expectancy' and not ok for name, ok, _ in out['checks'])


def test_no_go_on_daily_cap_breach(tmp_path):
    # 40 winners overall, but 20 losers stacked on ONE day = -$1200 (> $1000 cap).
    trades = _good_trades(100)
    trades += [(-0.6, -60.0, '2027-03-25') for _ in range(20)]
    stats = compute_live_stats([_write_log(tmp_path, trades)])
    assert stats['cap_breach_days'] == 1
    out = gate(stats)
    assert out['verdict'] == 'NO_GO'
    assert any(name == 'daily_cap_held' and not ok for name, ok, _ in out['checks'])


def test_aggregates_multiple_logs(tmp_path):
    a = tmp_path / 'a'; b = tmp_path / 'b'
    a.mkdir(); b.mkdir()
    la = _write_log(a, _good_trades(40)[:20])
    lb = _write_log(b, _good_trades(40)[20:])
    stats = compute_live_stats([la, lb])
    assert stats['n_trades'] == 40


def test_original_40_trade_sample_is_insufficient(tmp_path):
    stats = compute_live_stats([_write_log(tmp_path, _good_trades(40))])
    assert gate(stats)['verdict'] == 'INSUFFICIENT_DATA'


def test_fleet_profit_cannot_hide_account_breach(tmp_path):
    a = tmp_path / 'a'; b = tmp_path / 'b'
    a.mkdir(); b.mkdir()
    la = _write_log(a, _good_trades(100) + [(-12, -1200, '2027-01-01')])
    lb = _write_log(b, [(15, 1500, '2027-01-01')])
    stats = compute_live_stats([la, lb])
    assert stats['max_daily_loss'] == -1200
    assert gate(stats)['verdict'] == 'NO_GO'


def test_duplicate_fleet_trades_do_not_create_more_days(tmp_path):
    paths = []
    for i in range(10):
        folder = tmp_path / str(i); folder.mkdir()
        paths.append(_write_log(folder, _good_trades(20)))
    assert gate(compute_live_stats(paths))['verdict'] == 'INSUFFICIENT_DATA'


def test_missing_pnl_cannot_pass(tmp_path):
    path = _write_log(tmp_path, _good_trades(400))
    with open(path, 'a') as f:
        f.write(json.dumps({'action': 'trade_closed', 'total_r': 2,
                           'timestamp': '2026-01-01T10:00:00-05:00'}) + '\n')
    assert gate(compute_live_stats([path]))['verdict'] == 'NO_GO'


def test_clustered_losses_fail_confidence_check(tmp_path):
    trades = [(1.3 if i % 40 < 18 else -0.65,
               130 if i % 40 < 18 else -65, d)
              for i, (_, _, d) in enumerate(_good_trades(400))]
    stats = compute_live_stats([_write_log(tmp_path, trades)])
    assert stats['expectancy_r'] > 0.11
    assert gate(stats)['verdict'] == 'NO_GO'


def test_timestamp_is_converted_to_exchange_day(tmp_path):
    path = tmp_path / 'decisions.jsonl'
    path.write_text(json.dumps({'action': 'trade_closed', 'total_r': -1,
                               'pnl_usd': -600, 'timestamp': '2026-01-02T01:00:00Z'}) + '\n' +
                    json.dumps({'action': 'trade_closed', 'total_r': -1,
                                'pnl_usd': -600, 'timestamp': '2026-01-01T21:00:00-05:00'}) + '\n')
    stats = compute_live_stats([str(path)])
    assert stats['trading_days'] == 1
    assert stats['cap_breach_days'] == 1


def test_nonfinite_trade_is_invalid(tmp_path):
    path = _write_log(tmp_path, _good_trades(400) + [(float('nan'), 10, '2026-01-01')])
    stats = compute_live_stats([path])
    assert stats['invalid_records'] == 1
    assert gate(stats)['verdict'] == 'NO_GO'


def test_cli_returns_nonzero_without_evidence(tmp_path):
    from validate_forward import main
    assert main(['--log', str(tmp_path / 'missing.jsonl'), '--json']) == 2
