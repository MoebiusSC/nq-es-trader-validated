"""Check every strategy's signals against the unmodified pandas row path."""
from pathlib import Path
from dataclasses import asdict
import pandas as pd
import pytest
from config import Config
from data.loader import load_csv, build_daily_bars
from strategy.multi import MultiModelGenerator
from scripts.research_rows import ResearchFrame, accelerate_research


def test_scalar_and_slice_semantics():
    df = pd.DataFrame({'datetime': pd.date_range('2026-01-01', periods=3),
                       'close': [1.0, float('nan'), 3.0]})
    view = ResearchFrame(df)
    assert view.iloc[-1]['datetime'] == df.iloc[-1]['datetime']
    assert pd.isna(view.iloc[1].get('close'))
    assert view.iloc[1].get('absent', 17) == 17
    pd.testing.assert_frame_equal(view.iloc[:2], df.iloc[:2])


def test_all_model_signals_equal_pandas_path():
    path = Path('data/Dataset_NQ_1min_2022_2025.csv')
    if not path.exists():
        pytest.skip('Historical data not available')
    # Spread a manageable sample across years to exercise multiple regimes.
    raw = load_csv(str(path)).iloc[::175].reset_index(drop=True)
    daily = build_daily_bars(raw)
    daily['date'] = pd.to_datetime(daily['date']).dt.date
    normal = MultiModelGenerator(Config()).generate(raw, daily)
    fast = accelerate_research(MultiModelGenerator(Config())).generate(raw, daily)
    assert normal, 'Sample must exercise actual signals'
    assert [asdict(s) for s in fast] == [asdict(s) for s in normal]
