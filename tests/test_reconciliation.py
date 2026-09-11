"""
Unit test cho reconciliation/ — dùng DataFrame giả lập, KHÔNG gọi API thật.
Chạy: pytest tests/ (từ thư mục gốc project, sau khi `pip install pytest`)
"""
import sys
sys.path.append("..")

import pandas as pd

import config
from reconciliation.normalize import normalize_network, normalize_metabase, normalize_adjust, filter_excluded_dates
from reconciliation.merge import merge_sources
from reconciliation.flags import build_detail
from reconciliation.summary import summarize


def test_normalize_network_mapping():
    assert normalize_network("ALV") == "APPLOVIN"
    assert normalize_network("applovin") == "APPLOVIN"
    assert normalize_network(" ALV ") == "APPLOVIN"


def test_normalize_network_unknown_value_does_not_crash(capsys):
    result = normalize_network("SOME_NEW_NETWORK")
    assert result == "SOME_NEW_NETWORK"  # giữ nguyên, không raise
    captured = capsys.readouterr()
    assert "CẢNH BÁO" in captured.out  # nhưng phải in cảnh báo


def _make_pair(mb_roas_d7=0.20, adj_roas_d7=0.21, cohort_date="2026-08-01",
                campaign="Test Campaign", mb_network="APPLOVIN", adj_network="ALV"):
    df_mb = pd.DataFrame({
        "Cohort Date": [cohort_date],
        "Campaign": [campaign],
        "Network": [mb_network],
        "Cost": [1000.0],
        "Adjust Installs": [100],
        "ROAS D0": [0.10], "ROAS D3": [0.15], "ROAS D7": [mb_roas_d7], "ROAS D14": [0.25], "ROAS D28": [0.30],
        "Revenue D0": [100.0], "Revenue D3": [150.0], "Revenue D7": [200.0], "Revenue D14": [250.0], "Revenue D28": [300.0],
    })
    df_adjust = pd.DataFrame({
        "day": [cohort_date],
        "campaign_network": [campaign],
        "network": [adj_network],
        "network_cost": [1000.0],
        "installs": [100],
        "roas_ad_cal_d0": [0.10], "roas_ad_cal_d3": [0.15], "roas_ad_cal_d7": [adj_roas_d7],
        "roas_ad_cal_d14": [0.25], "roas_ad_cal_d28": [0.30],
        "ad_revenue_total_cal_d0": [100.0], "ad_revenue_total_cal_d3": [150.0],
        "ad_revenue_total_cal_d7": [200.0], "ad_revenue_total_cal_d14": [250.0],
        "ad_revenue_total_cal_d28": [300.0],
    })
    return df_mb, df_adjust


def test_merge_and_flag_end_to_end():
    df_mb, df_adjust = _make_pair(mb_roas_d7=0.20, adj_roas_d7=0.21)

    mb_norm = normalize_metabase(df_mb)
    adj_norm = normalize_adjust(df_adjust)
    merged = merge_sources(mb_norm, adj_norm)

    assert (merged["_merge"] == "both").sum() == 1  # phải join được, dù ALV vs APPLOVIN

    # Vô hiệu hoá maturity check để test thuần logic ratio (cohort giả không có
    # ý nghĩa "tuổi" thật, tránh N/A do chưa mature làm nhiễu test)
    config.EXCLUDE_IMMATURE_COHORTS = False
    detail = build_detail(merged)

    # ratio = 0.20 / 0.21 -> rel_diff_pct ~ -4.76%, dưới ngưỡng 5% -> OK
    row = detail[(detail["metric"] == "ROAS_D7")].iloc[0]
    assert row["flag"] == "OK"

    config.EXCLUDE_IMMATURE_COHORTS = True  # reset lại default cho test khác


def test_ratio_based_flag_discrepancy_when_over_threshold():
    df_mb, df_adjust = _make_pair(mb_roas_d7=0.20, adj_roas_d7=0.40)  # lệch gấp đôi

    mb_norm = normalize_metabase(df_mb)
    adj_norm = normalize_adjust(df_adjust)
    merged = merge_sources(mb_norm, adj_norm)

    config.EXCLUDE_IMMATURE_COHORTS = False
    detail = build_detail(merged)
    row = detail[(detail["metric"] == "ROAS_D7")].iloc[0]

    assert row["flag"] == "Discrepancy"
    assert row["ratio"] == 0.5
    config.EXCLUDE_IMMATURE_COHORTS = True


def test_join_key_mismatch_shows_up_as_only_mb():
    df_mb, df_adjust = _make_pair(campaign="Campaign A")
    df_adjust["campaign_network"] = "Campaign B"  # tên khác -> không join được

    mb_norm = normalize_metabase(df_mb)
    adj_norm = normalize_adjust(df_adjust)
    merged = merge_sources(mb_norm, adj_norm)

    assert (merged["_merge"] == "left_only").sum() == 1
    assert (merged["_merge"] == "both").sum() == 0


def test_filter_excluded_dates():
    df_mb, _ = _make_pair(cohort_date="2026-09-08")
    mb_norm = normalize_metabase(df_mb)
    filtered = filter_excluded_dates(mb_norm, ["2026-09-08"])
    assert len(filtered) == 0


def test_summarize_reads_from_flag_column_not_recomputed():
    df_mb, df_adjust = _make_pair(mb_roas_d7=0.20, adj_roas_d7=0.21)
    mb_norm = normalize_metabase(df_mb)
    adj_norm = normalize_adjust(df_adjust)
    merged = merge_sources(mb_norm, adj_norm)

    config.EXCLUDE_IMMATURE_COHORTS = False
    detail = build_detail(merged)
    result = summarize(detail, verbose=False)
    config.EXCLUDE_IMMATURE_COHORTS = True

    assert "by_campaign" in result and "overall" in result
    assert (result["overall"]["campaign"] == "ALL_CAMPAIGNS").all()
