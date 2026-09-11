"""
EDA (exploratory data analysis) cho bảng `detail` (long-format, output của
reconciliation.flags.build_detail). Mỗi hàm vừa in/trả về DataFrame tổng hợp,
vừa vẽ 1 biểu đồ matplotlib — gọi trực tiếp trong notebook, không cần thêm code.

Yêu cầu thêm matplotlib, seaborn (xem requirements.txt).
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

import config

# Metric có thể CỘNG DỒN có ý nghĩa (Cost, Installs, Revenue) — dùng cho so sánh
# tổng. KHÔNG gồm ROAS_* vì ROAS là tỷ lệ, cộng dồn không có ý nghĩa thống kê.
SUMMABLE_METRICS = ["COST", "INSTALLS"] + [f"REVENUE_D{d[1:]}" for d in config.ROAS_DAYS]


def _valid(detail: pd.DataFrame) -> pd.DataFrame:
    """Chỉ giữ dòng có flag hợp lệ (OK/Discrepancy) — loại các dòng N/A
    (thiếu dữ liệu / chưa mature), tránh làm sai lệch tổng và thống kê."""
    return detail[detail["flag"].isin(["OK", "Discrepancy"])]


# ---------------------------------------------------------------------------
# 1. So sánh TỔNG — Metabase vs Adjust (mới thêm, notebook tham khảo chưa có)
# ---------------------------------------------------------------------------
def compare_totals(detail: pd.DataFrame, metrics: list[str] | None = None) -> pd.DataFrame:
    """Tổng Installs/Cost/Revenue DX cộng dồn trên toàn bộ khoảng ngày đã chọn,
    so sánh Metabase vs Adjust. Trả về DataFrame để dùng tiếp (VD ghi báo cáo)."""
    metrics = metrics or SUMMABLE_METRICS
    valid = _valid(detail)
    valid = valid[valid["metric"].isin(metrics)]

    totals = (
        valid.groupby("metric")
        .agg(mb_total=("mb_value", "sum"), adjust_total=("adjust_value", "sum"), n=("mb_value", "count"))
        .reset_index()
    )
    totals["rel_diff_pct"] = (totals["mb_total"] / totals["adjust_total"] - 1) * 100
    totals["metric"] = pd.Categorical(totals["metric"], categories=config.METRIC_ORDER, ordered=True)
    totals = totals.sort_values("metric").reset_index(drop=True)

    print("=== So sánh TỔNG (cộng dồn toàn bộ khoảng ngày) ===")
    print(totals.to_string(index=False))
    return totals


def plot_totals_comparison(totals: pd.DataFrame) -> None:
    """Bar chart 2 cột (Metabase / Adjust) cạnh nhau cho từng metric."""
    x = np.arange(len(totals))
    width = 0.35

    fig, ax = plt.subplots(figsize=(max(8, 1.3 * len(totals)), 5))
    ax.bar(x - width / 2, totals["mb_total"], width, label="Metabase", color="steelblue")
    ax.bar(x + width / 2, totals["adjust_total"], width, label="Adjust", color="coral")
    ax.set_xticks(x)
    ax.set_xticklabels(totals["metric"], rotation=45, ha="right")
    ax.set_ylabel("Tổng giá trị (cộng dồn toàn bộ khoảng ngày)")
    ax.set_title("So sánh Tổng: Metabase vs Adjust")
    ax.legend()
    for i, (mb, adj) in enumerate(zip(totals["mb_total"], totals["adjust_total"])):
        ax.text(i - width / 2, mb, f"{mb:,.0f}", ha="center", va="bottom", fontsize=8)
        ax.text(i + width / 2, adj, f"{adj:,.0f}", ha="center", va="bottom", fontsize=8)
    plt.tight_layout()
    plt.show()


# ---------------------------------------------------------------------------
# 2. Tổng quan Campaign — số lượng, số ngày/campaign
# ---------------------------------------------------------------------------
def campaign_overview(detail: pd.DataFrame) -> pd.DataFrame:
    """Đếm số campaign đang đối chiếu, số ngày (cohort) mỗi campaign có dữ liệu.
    Dùng 1 dòng/(cohort_date, campaign) để tránh đếm trùng do detail lặp lại
    theo từng metric."""
    cohort_master = detail.drop_duplicates(subset=["cohort_date", "campaign"])[["cohort_date", "campaign"]]

    overview = (
        cohort_master.groupby("campaign")["cohort_date"]
        .agg(n_days="count", first_date="min", last_date="max")
        .sort_values("n_days", ascending=False)
    )

    print(f"Số lượng Campaign đang đối chiếu: {detail['campaign'].nunique()}")
    print(overview.to_string())
    return overview


def plot_campaign_overview(overview: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, max(3, 0.5 * len(overview))))
    sorted_days = overview["n_days"].sort_values()
    sorted_days.plot(kind="barh", ax=ax, color="steelblue")
    ax.set_xlabel("Số ngày (cohort) có dữ liệu")
    ax.set_title("Số ngày chạy mỗi Campaign")
    for i, v in enumerate(sorted_days):
        ax.text(v, i, f" {v}", va="center")
    plt.tight_layout()
    plt.show()


# ---------------------------------------------------------------------------
# 3. Heatmap % Discrepancy theo Campaign x Metric
# ---------------------------------------------------------------------------
def plot_discrepancy_heatmap(summary_by_campaign: pd.DataFrame) -> pd.DataFrame:
    """Input: summary_by_campaign từ reconciliation.summary.summarize()["by_campaign"].
    Trả về pivot table đã dùng để vẽ, để bạn có thể in/lưu lại riêng nếu cần."""
    pivot = summary_by_campaign.pivot(index="campaign", columns="metric", values="pct_discrepancy")
    pivot = pivot[[m for m in config.METRIC_ORDER if m in pivot.columns]]

    fig, ax = plt.subplots(figsize=(max(8, 1.1 * len(pivot.columns)), max(3, 1 * len(pivot))))
    sns.heatmap(
        pivot, annot=True, fmt=".1f", cmap="RdYlGn_r", center=25,
        vmin=0, vmax=100, linewidths=0.5, cbar_kws={"label": "% Discrepancy"}, ax=ax,
    )
    ax.set_title("Heatmap % Discrepancy theo Campaign x Metric")
    ax.set_xlabel("")
    ax.set_ylabel("")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.show()
    return pivot


# ---------------------------------------------------------------------------
# 4. Phân tích theo Metric — toàn hệ thống (gộp mọi campaign)
# ---------------------------------------------------------------------------
def plot_rel_diff_boxplot(detail: pd.DataFrame) -> None:
    """Boxplot phân bố rel_diff_pct theo từng metric — thấy được cả trung bình
    lẫn độ phân tán/outlier, đường đỏ chấm là ngưỡng ±THRESHOLD_PCT."""
    valid = _valid(detail)
    order = [m for m in config.METRIC_ORDER if m in valid["metric"].unique()]

    fig, ax = plt.subplots(figsize=(12, 5))
    sns.boxplot(data=valid, x="metric", y="rel_diff_pct", order=order, ax=ax)
    ax.axhline(0, color="gray", linestyle="--", linewidth=1)
    ax.axhline(config.THRESHOLD_PCT, color="red", linestyle=":", linewidth=1)
    ax.axhline(-config.THRESHOLD_PCT, color="red", linestyle=":", linewidth=1)
    ax.set_ylabel("rel_diff_pct (%)")
    ax.set_xlabel("")
    ax.set_title(f"Phân bố sai số tương đối theo Metric (ngưỡng = ±{config.THRESHOLD_PCT}%)")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.show()


def plot_overall_discrepancy_bar(summary_overall: pd.DataFrame) -> None:
    """Input: summary_overall từ reconciliation.summary.summarize()["overall"]."""
    order = [m for m in config.METRIC_ORDER if m in summary_overall["metric"].astype(str).unique()]
    so_plot = summary_overall.set_index("metric").reindex(order)

    fig, ax = plt.subplots(figsize=(10, 4))
    so_plot["pct_discrepancy"].plot(kind="bar", ax=ax, color="coral")
    ax.set_ylabel("% Discrepancy")
    ax.set_xlabel("")
    ax.set_title("% Discrepancy tổng quan theo Metric (toàn bộ Campaign)")
    for i, v in enumerate(so_plot["pct_discrepancy"]):
        ax.text(i, v, f"{v:.1f}%", ha="center", va="bottom", fontsize=9)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.show()


# ---------------------------------------------------------------------------
# 5. Xu hướng theo thời gian
# ---------------------------------------------------------------------------
def plot_ratio_trend(detail: pd.DataFrame, metrics: list[str] | None = None) -> None:
    """Line chart trung bình ratio (mb/adj) mỗi ngày, cho vài metric đại diện.
    ratio=1 (đường nét đứt) nghĩa là khớp hoàn toàn."""
    metrics = metrics or ["ROAS_D0", "REVENUE_D0", "INSTALLS"]
    valid = _valid(detail)
    trend = valid.groupby(["cohort_date", "metric"])["ratio"].mean().reset_index()

    fig, ax = plt.subplots(figsize=(12, 5))
    for m in metrics:
        sub = trend[trend["metric"] == m].sort_values("cohort_date")
        if len(sub) > 0:
            ax.plot(sub["cohort_date"], sub["ratio"], marker="o", markersize=3, label=m)
    ax.axhline(1.0, color="gray", linestyle="--", linewidth=1, label="ratio = 1 (khớp hoàn toàn)")
    ax.set_ylabel("Trung bình ratio (mb/adj) trong ngày")
    ax.set_xlabel("Cohort Date")
    ax.set_title("Xu hướng ratio (mb/adj) theo thời gian")
    ax.legend()
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.show()