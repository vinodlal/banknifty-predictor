import pandas as pd

from core.features.drivers import align_by_date, pct_corr
from tests.conftest import make_df


def test_align_by_date_matches_only_overlapping_dates():
    # target has 5 daily bars; driver has different coverage/order but shares
    # 3 of those calendar dates -- alignment must pick exactly those 3, by
    # date, not by row position.
    target = make_df([{"o": 100 + i, "h": 100 + i, "l": 100 + i, "c": 100 + i} for i in range(5)])
    driver_rows = target.iloc[[1, 2, 4]].copy()  # only 3 overlapping dates, out of positional order
    driver = pd.DataFrame({
        "ts": [driver_rows["ts"].iloc[2], driver_rows["ts"].iloc[0], driver_rows["ts"].iloc[1]],
        "close": [999, 111, 222],  # deliberately different values/order than target
    })
    t_aligned, d_aligned = align_by_date(target, driver)
    assert len(t_aligned) == 3
    # sorted by date: target's day-1 (101) pairs with driver's 111,
    # day-2 (102) pairs with 222, day-4 (104) pairs with 999
    assert list(t_aligned.values) == [101, 102, 104]
    assert list(d_aligned.values) == [111, 222, 999]


def test_pct_corr_works_on_aligned_output():
    target = make_df([{"o": v, "h": v, "l": v, "c": v} for v in [100, 110, 99, 108.9]])
    driver = pd.DataFrame({"ts": target["ts"], "close": [100, 90, 99, 89.1]})
    t_aligned, d_aligned = align_by_date(target, driver)
    assert pct_corr(t_aligned, d_aligned, window=3) == -1.0
