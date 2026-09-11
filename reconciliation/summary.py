"""
Tổng hợp bảng `detail` (long-format) theo 2 tầng — Campaign x Metric, và toàn hệ thống
theo Metric — để không bị "trung bình hoá" che mất campaign đang có vấn đề riêng.

LUÔN đọc % discrepancy từ cột `flag` có sẵn, không tự tính lại từ `rel_diff_pct`
(đây từng là 1 bug thực tế: summary không phản ánh đúng flag đã cập nhật).
"""
import pandas as pd

import config


def _build_summary(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    s = (
        df.groupby(group_cols)
        .agg(
            n_valid=("flag", "count"),
            mean_abs_diff=("abs_diff", lambda x: x.abs().mean()),
            mean_ratio=("ratio", "mean"),
            mean_abs_rel_diff_pct=("rel_diff_pct", lambda x: x.abs().mean()),
            median_abs_rel_diff_pct=("rel_diff_pct", lambda x: x.abs().median()),
            p90_abs_rel_diff_pct=("rel_diff_pct", lambda x: x.abs().quantile(0.9)),
            pct_discrepancy=("flag", lambda x: (x == "Discrepancy").mean() * 100),
        )
        .round(4)
        .reset_index()
    )
    s["metric"] = pd.Categorical(s["metric"], categories=config.METRIC_ORDER, ordered=True)
    return s.sort_values(group_cols).reset_index(drop=True)


def summarize(detail: pd.DataFrame, verbose: bool = True) -> dict:
    """Chỉ tổng hợp trên các dòng có flag hợp lệ (OK/Discrepancy) — các dòng
    "N/A (...)" (thiếu dữ liệu / chưa mature) bị loại khỏi mẫu tính %, vì đưa
    vào sẽ làm loãng con số theo hướng sai (trông như "ít lỗi hơn" trong khi
    thực ra là "chưa đủ dữ liệu để biết")."""
    valid = detail[detail["flag"].isin(["OK", "Discrepancy"])]

    by_campaign = _build_summary(valid, ["campaign", "metric"])
    overall = _build_summary(valid, ["metric"])
    overall.insert(0, "campaign", "ALL_CAMPAIGNS")

    if verbose:
        print("=== Tổng hợp theo từng Campaign ===")
        print(by_campaign.to_string(index=False))
        print("\n=== Tổng hợp toàn hệ thống (gộp hết campaign) ===")
        print(overall.to_string(index=False))

    return {"by_campaign": by_campaign, "overall": overall}


def top_discrepancy(detail: pd.DataFrame, top_n: int = 20, per_campaign: int | None = 5) -> dict:
    """Trả về top N dòng lệch nhiều nhất — toàn bộ, và (tuỳ chọn) top-K riêng
    theo từng campaign, để không bị 1 campaign lớn "chiếm hết" top toàn bộ."""
    cols = ["cohort_date", "network", "campaign", "metric", "mb_value", "adjust_value", "abs_diff", "rel_diff_pct"]

    ranked = (
        detail[detail["flag"] == "Discrepancy"]
        .assign(abs_rel_diff_pct=lambda d: d["rel_diff_pct"].abs())
        .sort_values("abs_rel_diff_pct", ascending=False)
    )

    result = {"top_overall": ranked.head(top_n)[cols]}

    if per_campaign:
        ranked = ranked.copy()
        ranked["rank_in_campaign"] = ranked.groupby("campaign")["abs_rel_diff_pct"].rank(
            method="first", ascending=False
        )
        result["top_per_campaign"] = (
            ranked[ranked["rank_in_campaign"] <= per_campaign]
            .sort_values(["campaign", "rank_in_campaign"])[cols]
        )

    return result
