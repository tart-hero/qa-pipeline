"""
Tính bảng đối chiếu dạng LONG-FORMAT (1 dòng = 1 cohort x 1 metric).

[CHỐT — xem docs/reconciliation.md và QA_GameA_Android_ALV.ipynb]
- Sai số tương đối THỐNG NHẤT cho MỌI metric (ROAS, Revenue, Cost, Installs):
      ratio = mb_value / adj_value
      rel_diff_pct = (ratio - 1) * 100
      flag = "Discrepancy" nếu |rel_diff_pct| > config.THRESHOLD_PCT, ngược lại "OK"
  (Đây là bản thay thế cho cách tính absolute-diff percentage-point trước đó —
  KHÔNG dùng nữa vì không khớp với threshold chuẩn ±5% tương đối của dự án.)
- Cohort chưa đủ "tuổi" cho mốc DX bị loại khỏi so sánh dựa trên Cohort Age
  (= DATA_ASOF_DATE - Cohort Date), KHÔNG chỉ dựa vào NaN — vì Adjust Dashboard
  có thể carry-forward giá trị cũ cho cohort chưa mature thay vì trả NULL,
  so trực tiếp sẽ ra sai số ảo gần -100%.
"""
from datetime import date as _date

import numpy as np
import pandas as pd

import config


def _resolve_as_of_date() -> _date:
    if config.DATA_ASOF_DATE:
        return pd.to_datetime(config.DATA_ASOF_DATE).date()
    return _date.today()


def build_detail(merged: pd.DataFrame, metric_map: dict) -> pd.DataFrame:
    """
    Input:
      merged: DataFrame đã merge (outer join) từ reconciliation.merge.merge_sources().
        Dùng nguyên `merged` (bao gồm cả các dòng only_mb/only_adj), KHÔNG lọc
        trước "_merge == both" — các dòng lệch join sẽ tự động ra flag
        "N/A (thiếu dữ liệu)" vì 1 trong 2 giá trị mb_val/adj_val là NaN, giữ được
        đầy đủ thông tin để debug thay vì âm thầm loại bỏ.
      metric_map: dict metric_name -> (cột Metabase, cột Adjust), lấy từ
        config.get_metric_map(game_key) — PHỤ THUỘC game vì mỗi game có thể có
        revenue_scope khác nhau (Ad-only vs Total, xem config.py).

    Output: DataFrame long-format với các cột:
    cohort_date, network, campaign, metric, cohort_age_days, is_immature,
    mb_value, adjust_value, abs_diff, ratio, rel_diff_pct, flag
    """
    as_of_date = _resolve_as_of_date()
    print(f"Cohort Age tính theo DATA_ASOF_DATE = {as_of_date}"
          + (" (config.DATA_ASOF_DATE để None -> dùng ngày hệ thống)" if not config.DATA_ASOF_DATE else ""))
    print(f"EXCLUDE_IMMATURE_COHORTS = {config.EXCLUDE_IMMATURE_COHORTS}")
    print(f"[CHỐT] Sai số tương đối ratio = mb/adj. Ngưỡng Discrepancy: "
          f"|rel_diff_pct| > {config.THRESHOLD_PCT}%")

    rows = []
    n_immature_excluded = 0

    for _, r in merged.iterrows():
        cohort_date = r["date"]
        network = r["network_key"]
        campaign = r["campaign_key"]

        cohort_age_days = (as_of_date - cohort_date).days if pd.notna(cohort_date) else np.nan

        for metric, (mb_col, adj_col) in metric_map.items():
            mb_val = r.get(mb_col, np.nan)
            adj_val = r.get(adj_col, np.nan)

            required_day = config.MATURITY_DAY_MAP.get(metric)  # None cho COST/INSTALLS
            is_immature = bool(
                config.EXCLUDE_IMMATURE_COHORTS
                and required_day is not None
                and pd.notna(cohort_age_days)
                and cohort_age_days < required_day
            )

            if is_immature:
                abs_diff, ratio, rel_diff_pct = np.nan, np.nan, np.nan
                flag = f"N/A (cohort {cohort_age_days}d tuổi < D{required_day} — chưa mature)"
                n_immature_excluded += 1
            elif pd.isna(mb_val) or pd.isna(adj_val):
                abs_diff, ratio, rel_diff_pct = np.nan, np.nan, np.nan
                flag = "N/A (thiếu dữ liệu / cohort chưa đủ maturity)"
            elif adj_val == 0:
                abs_diff, ratio, rel_diff_pct = np.nan, np.nan, np.nan
                flag = "N/A (adjust = 0, không chia được)"
            else:
                abs_diff = mb_val - adj_val
                ratio = mb_val / adj_val
                rel_diff_pct = (ratio - 1) * 100.0
                flag = "Discrepancy" if abs(rel_diff_pct) > config.THRESHOLD_PCT else "OK"

            rows.append({
                "cohort_date": cohort_date,
                "network": network,
                "campaign": campaign,
                "metric": metric,
                "cohort_age_days": cohort_age_days,
                "is_immature": is_immature,
                "mb_value": round(mb_val, 6) if pd.notna(mb_val) else mb_val,
                "adjust_value": round(adj_val, 6) if pd.notna(adj_val) else adj_val,
                "abs_diff": round(abs_diff, 6) if pd.notna(abs_diff) else abs_diff,
                "ratio": round(ratio, 6) if pd.notna(ratio) else ratio,
                "rel_diff_pct": round(rel_diff_pct, 4) if pd.notna(rel_diff_pct) else rel_diff_pct,
                "flag": flag,
            })

    detail = pd.DataFrame(rows).sort_values(["cohort_date", "metric"]).reset_index(drop=True)
    print(f"\nBảng detail: {detail.shape[0]} dòng (= {merged.shape[0]} cohort x {len(metric_map)} chỉ số)")
    print(f"Số dòng bị loại vì cohort chưa đủ maturity: {n_immature_excluded}")
    return detail