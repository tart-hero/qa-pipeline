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

def _add_grid(ax) -> None:
    """Lưới mờ dùng chung cho mọi biểu đồ trong module này — giúp đọc giá trị
    trên trục dễ hơn mà không rối mắt (alpha thấp, đặt phía dưới các phần tử khác)."""
    ax.grid(True, alpha=0.3, linestyle="--", linewidth=0.5)
    ax.set_axisbelow(True)

def _metrics_present(valid: pd.DataFrame, metrics: list[str] | None) -> list[str]:
    """Danh sách metric cần vẽ, giữ đúng thứ tự config.METRIC_ORDER và chỉ gồm
    metric thực sự có dữ liệu hợp lệ."""
    present = set(valid["metric"].unique())
    if metrics is not None:
        missing = [m for m in metrics if m not in present]
        if missing:
            print(f"⚠️ Bỏ qua metric không có dữ liệu hợp lệ: {missing}")
        return [m for m in metrics if m in present]
    return [m for m in config.METRIC_ORDER if m in present]


def _short_campaign_labels(campaigns: list[str]) -> dict[str, str]:
    """Rút gọn tên campaign để làm nhãn trục x — tên thật rất dài và thường chỉ
    khác nhau ở phần giữa (VD "CDS Android - D28 AdROAS - 260131"), để nguyên
    thì nhãn chồng lên nhau không đọc được. Cắt phần tiền tố/hậu tố giống nhau
    ở MỌI campaign, phần còn lại mới là thứ phân biệt chúng."""
    if len(campaigns) <= 1:
        return {c: (c[:28] + "…" if len(c) > 28 else c) for c in campaigns}

    tokens = [c.split() for c in campaigns]
    n_pre = 0
    while all(len(t) > n_pre + 1 and t[n_pre] == tokens[0][n_pre] for t in tokens):
        n_pre += 1
    n_suf = 0
    while all(len(t) > n_pre + n_suf + 1 and t[-1 - n_suf] == tokens[0][-1 - n_suf] for t in tokens):
        n_suf += 1

    labels = {}
    for c, t in zip(campaigns, tokens):
        short = " ".join(t[n_pre:len(t) - n_suf] if n_suf else t[n_pre:])
        labels[c] = short if short else c
    return labels


def _auto_range(values: pd.Series) -> tuple[float, float]:
    """Khoảng hiển thị hợp lý cho rel_diff_pct: [Q1 - 3*IQR, Q3 + 3*IQR].
    Giữ trọn thân + râu của box (râu chỉ tới 1.5*IQR), chỉ cắt outlier cực đoan
    (VD rel_diff = -100% khi 1 phía bằng 0) vốn làm dẹp toàn bộ phần còn lại."""
    q1, q3 = np.nanpercentile(values, [25, 75])
    iqr = q3 - q1
    lo, hi = q1 - 3 * iqr, q3 + 3 * iqr
    # Sàn tối thiểu: metric khớp gần như tuyệt đối (COST) có IQR = 0, không có
    # sàn thì khung dẹp thành 1 đường và mất luôn 2 vạch ngưỡng.
    floor = config.THRESHOLD_PCT * 1.5
    return min(lo, -floor), max(hi, floor)


def _apply_ylim(ax, values: pd.Series, ylim) -> None:
    """Giới hạn trục y cho dễ đọc, nhưng KHÔNG im lặng giấu dữ liệu: số điểm
    nằm ngoài khung luôn được ghi chú ngay trên biểu đồ.

    ylim=None          -> tự co theo `_auto_range`
    ylim=False         -> để matplotlib tự scale, thấy đủ mọi outlier
    ylim=(low, high)   -> đặt tay
    """
    if ylim is False or len(values) == 0:
        return

    lo, hi = _auto_range(values) if ylim is None else ylim

    n_out = int(((values < lo) | (values > hi)).sum())
    ax.set_ylim(lo, hi)
    if n_out:
        ax.text(
            0.99, 0.02, f"{n_out} điểm ngoài khung", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=7, color="dimgray", style="italic",
            bbox={"facecolor": "white", "alpha": 0.7, "edgecolor": "none", "pad": 1},
        )


def _metric_grid(metrics: list[str], ncols: int, panel_w: float, panel_h: float):
    """Lưới subplot 1 ô / 1 metric — dùng chung cho các biểu đồ distribution."""
    ncols = min(ncols, len(metrics))
    nrows = int(np.ceil(len(metrics) / ncols))
    fig, axes = plt.subplots(
        nrows, ncols, figsize=(panel_w * ncols, panel_h * nrows), squeeze=False
    )
    flat = axes.ravel()
    for ax in flat[len(metrics):]:
        ax.set_visible(False)
    return fig, flat


def _draw_threshold_lines(ax) -> None:
    ax.axhline(0, color="gray", linestyle="--", linewidth=1)
    ax.axhline(config.THRESHOLD_PCT, color="red", linestyle=":", linewidth=1)
    ax.axhline(-config.THRESHOLD_PCT, color="red", linestyle=":", linewidth=1)


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
    order = _metrics_present(valid, None)

    fig, ax = plt.subplots(figsize=(12, 5))
    sns.boxplot(data=valid, x="metric", y="rel_diff_pct", order=order, ax=ax)
    _draw_threshold_lines(ax)
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
    """[TOTAL — gộp mọi Campaign] Line chart trung bình ratio (mb/adj) mỗi ngày,
    cho vài metric đại diện, gộp chung tất cả campaign. ratio=1 (đường nét đứt)
    nghĩa là khớp hoàn toàn."""
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
    ax.set_title("Xu hướng ratio (mb/adj) theo thời gian — TOTAL (gộp mọi Campaign)")
    ax.legend()
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.show()


def plot_ratio_trend_by_campaign(
    detail: pd.DataFrame,
    metric: str = "ROAS_D0",
    campaigns: list[str] | None = None,
) -> None:
    """[THEO TỪNG CAMPAIGN] Line chart ratio (mb/adj) mỗi ngày, 1 đường/campaign,
    cho ĐÚNG 1 metric — vẽ nhiều campaign x nhiều metric cùng lúc sẽ quá rối,
    không đọc được. Đổi `metric` để xem metric khác (VD "COST", "REVENUE_D7").

    `campaigns=None` -> vẽ tất cả campaign hiện có. Nếu có nhiều campaign
    (>8), cân nhắc truyền danh sách cụ thể để biểu đồ không quá rối.
    """
    valid = _valid(detail)
    valid = valid[valid["metric"] == metric]

    if campaigns is None:
        campaigns = sorted(valid["campaign"].unique())
    if len(campaigns) > 8:
        print(f"⚠️ CẢNH BÁO: đang vẽ {len(campaigns)} campaign cùng lúc, biểu đồ có thể rối. "
              f"Cân nhắc truyền `campaigns=[...]` để giới hạn lại.")

    trend = (
        valid[valid["campaign"].isin(campaigns)]
        .groupby(["cohort_date", "campaign"])["ratio"]
        .mean()
        .reset_index()
    )

    fig, ax = plt.subplots(figsize=(12, 5))
    for c in campaigns:
        sub = trend[trend["campaign"] == c].sort_values("cohort_date")
        if len(sub) > 0:
            ax.plot(sub["cohort_date"], sub["ratio"], marker="o", markersize=3, label=c)
    ax.axhline(1.0, color="gray", linestyle="--", linewidth=1, label="ratio = 1 (khớp hoàn toàn)")
    ax.set_ylabel("Trung bình ratio (mb/adj) trong ngày")
    ax.set_xlabel("Cohort Date")
    ax.set_title(f"Xu hướng ratio (mb/adj) theo thời gian — THEO CAMPAIGN — metric: {metric}")
    ax.legend(loc="best", fontsize=8)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.show()


# ---------------------------------------------------------------------------
# 6. Phân bố sai số của TỪNG metric — bóc tách theo Campaign / theo Cohort
# ---------------------------------------------------------------------------
# Khác mục 4 (`plot_rel_diff_boxplot` gộp mọi campaign & mọi ngày vào 1 box/metric):
# ở đây mỗi metric có 1 ô riêng, bên trong tách tiếp theo campaign hoặc theo cohort,
# để trả lời "sai số của metric này đến từ campaign nào / giai đoạn nào".
def rel_diff_stats(
    detail: pd.DataFrame,
    by: str | None = "campaign",
    metrics: list[str] | None = None,
    freq: str = "W",
) -> pd.DataFrame:
    """Bảng thống kê mô tả sai số `rel_diff_pct` của từng metric, bóc theo
    `by="campaign"` / `by="cohort"` (gom cohort_date theo `freq`) / `by=None`
    (chỉ theo metric). Đây là phần SỐ đi kèm các biểu đồ bên dưới — dùng khi cần
    trích số cụ thể vào báo cáo thay vì đọc ước lượng trên hình.

    Cột `pct_discrepancy` = % số dòng vượt ngưỡng ±THRESHOLD_PCT trong nhóm đó.
    """
    valid = _valid(detail).copy()
    metrics = _metrics_present(valid, metrics)
    valid = valid[valid["metric"].isin(metrics)]

    keys = ["metric"]
    if by == "campaign":
        keys.append("campaign")
    elif by == "cohort":
        valid["cohort_period"] = _cohort_period(valid["cohort_date"], freq)
        keys.append("cohort_period")
    elif by is not None:
        raise ValueError(f"`by` phải là 'campaign' | 'cohort' | None, nhận được: {by!r}")

    valid["is_disc"] = valid["flag"] == "Discrepancy"
    stats = (
        valid.groupby(keys, observed=True)
        .agg(
            n=("rel_diff_pct", "count"),
            mean=("rel_diff_pct", "mean"),
            median=("rel_diff_pct", "median"),
            std=("rel_diff_pct", "std"),
            p05=("rel_diff_pct", lambda s: s.quantile(0.05)),
            p95=("rel_diff_pct", lambda s: s.quantile(0.95)),
            min=("rel_diff_pct", "min"),
            max=("rel_diff_pct", "max"),
            pct_discrepancy=("is_disc", lambda s: 100 * s.mean()),
        )
        .reset_index()
    )
    stats["metric"] = pd.Categorical(stats["metric"], categories=config.METRIC_ORDER, ordered=True)
    return stats.sort_values(keys).reset_index(drop=True)


def _cohort_period(cohort_date: pd.Series, freq: str) -> pd.Series:
    """Gom cohort_date thành nhóm theo tuần/tháng. Mỗi ngày chỉ có vài dòng
    (= số campaign), vẽ boxplot theo từng NGÀY gần như vô nghĩa — gom theo tuần
    mới đủ mẫu để nhìn ra hình dạng phân bố."""
    dates = pd.to_datetime(cohort_date)
    if freq.upper().startswith("D"):
        return dates.dt.strftime("%Y-%m-%d")
    # Period dùng alias "M", trong khi resample() của pandas ≥2.2 dùng "ME" — nhận
    # cả 2 để không phải nhớ đang gọi API nào.
    freq = "M" if freq.upper() in {"M", "ME"} else freq
    period = dates.dt.to_period(freq)
    if freq.upper().startswith("W"):
        # Period tuần in ra dạng "2026-07-13/2026-07-19" — quá dài làm nhãn trục x,
        # chỉ lấy ngày đầu tuần (vẫn sort đúng theo thứ tự thời gian).
        return period.dt.start_time.dt.strftime("%Y-%m-%d")
    return period.astype(str)


def plot_rel_diff_dist_by_campaign(
    detail: pd.DataFrame,
    metrics: list[str] | None = None,
    campaigns: list[str] | None = None,
    ylim=None,
    ncols: int = 4,
) -> None:
    """[THEO CAMPAIGN] Lưới biểu đồ 1 ô / 1 metric; trong mỗi ô là boxplot phân bố
    `rel_diff_pct` của từng campaign (mỗi điểm = 1 cohort_date).

    Đọc hình: box nằm lệch hẳn khỏi đường 0 -> campaign đó lệch có HỆ THỐNG
    (nghi vấn mapping/scope sai). Box bám quanh 0 nhưng kéo dài -> lệch do vài
    ngày cá biệt, nên soi tiếp bằng `top_discrepancy`.

    `ylim`: None = tự co khung theo p2–p98 (ghi chú số điểm ngoài khung),
    False = hiện đủ mọi outlier, hoặc truyền tay (low, high).
    """
    valid = _valid(detail)
    if campaigns is not None:
        valid = valid[valid["campaign"].isin(campaigns)]
    metrics = _metrics_present(valid, metrics)
    if not metrics:
        print("Không có metric nào có dữ liệu hợp lệ để vẽ.")
        return

    order = campaigns if campaigns is not None else sorted(valid["campaign"].unique())
    order = [c for c in order if c in set(valid["campaign"])]
    labels = _short_campaign_labels(order)

    fig, axes = _metric_grid(metrics, ncols, panel_w=3.6, panel_h=3.4)
    for ax, m in zip(axes, metrics):
        sub = valid[valid["metric"] == m]
        sns.boxplot(
            data=sub, x="campaign", y="rel_diff_pct", order=order, hue="campaign",
            hue_order=order, palette="tab10", legend=False, fliersize=2, ax=ax,
        )
        # Chồng thêm từng điểm: số cohort/campaign khá ít, chỉ nhìn box dễ tưởng
        # phân bố dày hơn thực tế.
        sns.stripplot(
            data=sub, x="campaign", y="rel_diff_pct", order=order,
            color="black", size=2, alpha=0.35, jitter=0.2, ax=ax,
        )
        _draw_threshold_lines(ax)
        _apply_ylim(ax, sub["rel_diff_pct"], ylim)
        ax.set_title(m, fontsize=10)
        ax.set_xlabel("")
        ax.set_ylabel("rel_diff_pct (%)", fontsize=8)
        ax.set_xticks(range(len(order)))
        ax.set_xticklabels([labels[c] for c in order], rotation=30, ha="right", fontsize=7)
        ax.tick_params(axis="y", labelsize=8)

    fig.suptitle(
        f"Phân bố sai số từng Metric — THEO CAMPAIGN (mỗi điểm = 1 cohort_date, "
        f"ngưỡng ±{config.THRESHOLD_PCT}%)",
        fontsize=12,
    )
    plt.tight_layout()
    plt.show()


def plot_rel_diff_dist_by_cohort(
    detail: pd.DataFrame,
    metrics: list[str] | None = None,
    freq: str = "W",
    ylim=None,
    ncols: int = 4,
) -> None:
    """[THEO COHORT] Lưới biểu đồ 1 ô / 1 metric; trong mỗi ô là boxplot phân bố
    `rel_diff_pct` theo nhóm cohort_date (mặc định gom theo TUẦN — `freq="D"` để
    xem theo ngày, `freq="M"` theo tháng).

    Đọc hình: các box trôi dần theo thời gian -> sai số phát sinh từ 1 mốc cụ thể
    (đổi SDK/mart/tracking), nên đối chiếu mốc đó trước. Box cao đều từ đầu tới
    cuối -> lệch mang tính cấu trúc, không phải sự cố theo ngày.
    """
    valid = _valid(detail).copy()
    metrics = _metrics_present(valid, metrics)
    if not metrics:
        print("Không có metric nào có dữ liệu hợp lệ để vẽ.")
        return

    valid["cohort_period"] = _cohort_period(valid["cohort_date"], freq)
    order = sorted(valid["cohort_period"].unique())

    med_n = valid.groupby(["metric", "cohort_period"], observed=True).size().median()
    if med_n < 5:
        print(f"⚠️ Mỗi nhóm cohort chỉ có ~{med_n:.0f} điểm — box gần như vô nghĩa. "
              f"Dùng freq='W' (tuần) hoặc 'M' (tháng) để gom thêm mẫu.")

    fig, axes = _metric_grid(metrics, ncols, panel_w=max(3.6, 0.45 * len(order)), panel_h=3.4)
    for ax, m in zip(axes, metrics):
        sub = valid[valid["metric"] == m]
        sns.boxplot(
            data=sub, x="cohort_period", y="rel_diff_pct", order=order,
            color="steelblue", fliersize=2, ax=ax,
        )
        sns.stripplot(
            data=sub, x="cohort_period", y="rel_diff_pct", order=order,
            color="black", size=2, alpha=0.35, jitter=0.2, ax=ax,
        )
        _draw_threshold_lines(ax)
        _apply_ylim(ax, sub["rel_diff_pct"], ylim)
        ax.set_title(m, fontsize=10)
        ax.set_xlabel("")
        ax.set_ylabel("rel_diff_pct (%)", fontsize=8)
        ax.tick_params(axis="x", rotation=90, labelsize=7)
        ax.tick_params(axis="y", labelsize=8)

    freq_label = {"D": "ngày", "W": "tuần — nhãn là ngày đầu tuần", "M": "tháng"}.get(
        freq.upper()[:1], freq
    )
    fig.suptitle(
        f"Phân bố sai số từng Metric — THEO COHORT (gom theo {freq_label}, "
        f"ngưỡng ±{config.THRESHOLD_PCT}%)",
        fontsize=12,
    )
    plt.tight_layout()
    plt.show()


def plot_rel_diff_hist(
    detail: pd.DataFrame,
    metrics: list[str] | None = None,
    bins: int = 30,
    xlim=None,
    ncols: int = 4,
) -> None:
    """Histogram phân bố `rel_diff_pct` của từng metric (gộp mọi campaign & cohort)
    — xem HÌNH DẠNG phân bố mà boxplot không cho thấy: lệch 1 phía, hai đỉnh, hay
    đối xứng quanh 0. Vùng xanh là dải trong ngưỡng ±THRESHOLD_PCT (= flag OK).
    """
    valid = _valid(detail)
    metrics = _metrics_present(valid, metrics)
    if not metrics:
        print("Không có metric nào có dữ liệu hợp lệ để vẽ.")
        return

    fig, axes = _metric_grid(metrics, ncols, panel_w=3.6, panel_h=3.0)
    for ax, m in zip(axes, metrics):
        sub = valid[valid["metric"] == m]["rel_diff_pct"]
        if xlim is False:
            lo, hi = sub.min(), sub.max()
        else:
            lo, hi = _auto_range(sub) if xlim is None else xlim
        clipped = sub[(sub >= lo) & (sub <= hi)]
        # `range=(lo, hi)`: không có nó, matplotlib chia bin theo range của DỮ LIỆU
        # -> metric khớp gần tuyệt đối (COST) ra cột mảnh như sợi chỉ, nhìn như trống.
        ax.hist(clipped, bins=bins, range=(lo, hi), color="steelblue",
                edgecolor="white", linewidth=0.4)
        ax.set_xlim(lo, hi)
        ax.axvspan(-config.THRESHOLD_PCT, config.THRESHOLD_PCT, color="green", alpha=0.10)
        ax.axvline(0, color="gray", linestyle="--", linewidth=1)
        ax.axvline(sub.median(), color="darkorange", linewidth=1.2)
        n_out = len(sub) - len(clipped)
        if n_out:
            ax.text(0.99, 0.95, f"{n_out} điểm ngoài khung", transform=ax.transAxes,
                    ha="right", va="top", fontsize=7, color="dimgray", style="italic")
        ax.set_title(f"{m}  (n={len(sub)}, median {sub.median():.1f}%)", fontsize=10)
        ax.set_xlabel("rel_diff_pct (%)", fontsize=8)
        ax.set_ylabel("Số cohort x campaign", fontsize=8)
        ax.tick_params(labelsize=8)

    fig.suptitle(
        f"Phân bố sai số từng Metric — histogram (vùng xanh = trong ngưỡng "
        f"±{config.THRESHOLD_PCT}%, vạch cam = median)",
        fontsize=12,
    )
    plt.tight_layout()
    plt.show()


 #---------------------------------------------------------------------------
# 7. Phân bố sai số — Histogram & ECDF
# ---------------------------------------------------------------------------
def _facet_grid_axes(n: int, ncols: int = 3, col_width: float = 5.0, row_height: float = 3.5):
    """Helper dùng chung: tạo lưới subplot n ô, tự tính số hàng, tắt các ô thừa."""
    ncols = min(ncols, n) if n > 0 else 1
    nrows = -(-n // ncols)  # ceil division
    fig, axes = plt.subplots(nrows, ncols, figsize=(col_width * ncols, row_height * nrows), squeeze=False)
    axes = axes.reshape(-1)
    for j in range(n, len(axes)):
        axes[j].axis("off")
    return fig, axes
 
 
def _draw_rel_diff_hist(ax, sub: pd.Series, bins: int, threshold: float) -> None:
    """Vẽ 1 ô histogram rel_diff_pct + đường ngưỡng, TRỤC X TỰ ĐỘNG THEO DỮ LIỆU THẬT.
 
    QUAN TRỌNG: ax.axvline() mặc định sẽ tự kéo dãn xlim để bao trọn vị trí đường
    vline (VD ±THRESHOLD_PCT=5), ngay cả khi dữ liệu thật hẹp hơn nhiều (VD Cost
    thường khớp gần tuyệt đối, rel_diff_pct chỉ trong khoảng ±0.02%). Nếu không ép
    lại xlim, cột histogram thật sẽ bị nén thành 1 sợi mỏng vô hình so với khung ±5
    quá rộng. Set xlim SAU CÙNG (sau khi vẽ hist + vline) để ghi đè phần tự co dãn đó.
    Nếu ngưỡng nằm ngoài phạm vi dữ liệu (dữ liệu quá tốt), đường ngưỡng đơn giản
    là không hiện trong khung nhìn — đúng ý nghĩa "sai số nằm sâu trong ngưỡng".
    """
    ax.hist(sub, bins=bins, color="steelblue", edgecolor="white")
    _add_grid(ax)
    ax.axvline(0, color="gray", linestyle="--", linewidth=1)
    ax.axvline(threshold, color="red", linestyle=":", linewidth=1)
    ax.axvline(-threshold, color="red", linestyle=":", linewidth=1)
 
    if len(sub) > 0:
        data_min, data_max = float(sub.min()), float(sub.max())
        spread = data_max - data_min
        pad = max(spread * 0.15, threshold * 0.02, 1e-6)
        ax.set_xlim(data_min - pad, data_max + pad)
 
 
def plot_rel_diff_histogram(
    detail: pd.DataFrame,
    metrics: list[str] | None = None,
    bins: int = 30,
) -> None:
    """[TẤT CẢ CAMPAIGN] Facet grid — 1 ô/metric, histogram phân bố rel_diff_pct
    gộp mọi campaign. Đường xám nét đứt = 0 (khớp hoàn toàn), đường đỏ chấm =
    ngưỡng ±THRESHOLD_PCT (chỉ hiện nếu nằm trong phạm vi dữ liệu thật)."""
    metrics = metrics or config.METRIC_ORDER
    valid = _valid(detail)
    metrics_present = [m for m in metrics if m in valid["metric"].unique()]
 
    fig, axes = _facet_grid_axes(len(metrics_present))
    for i, m in enumerate(metrics_present):
        sub = valid[valid["metric"] == m]["rel_diff_pct"].dropna()
        _draw_rel_diff_hist(axes[i], sub, bins, config.THRESHOLD_PCT)
        axes[i].set_title(f"{m}  (n={len(sub)})", fontsize=10)
        axes[i].set_xlabel("rel_diff_pct (%)")
 
    fig.suptitle(f"Phân bố sai số tương đối theo Metric — TẤT CẢ CAMPAIGN (ngưỡng ±{config.THRESHOLD_PCT}%)")
    plt.tight_layout()
    plt.show()
 
 
def plot_rel_diff_histogram_by_campaign(
    detail: pd.DataFrame,
    metric: str = "ROAS_D7",
    campaigns: list[str] | None = None,
    bins: int = 20,
) -> None:
    """[THEO TỪNG CAMPAIGN] Facet grid — 1 ô/campaign, cho ĐÚNG 1 metric (histogram
    không overlay được nhiều campaign trên cùng 1 trục như line chart — mỗi ô
    riêng mới đọc được). Đổi `metric` để xem chỉ số khác."""
    valid = _valid(detail)
    valid = valid[valid["metric"] == metric]
 
    if campaigns is None:
        campaigns = sorted(valid["campaign"].unique())
    if len(campaigns) > 12:
        print(f"⚠️ CẢNH BÁO: đang vẽ {len(campaigns)} campaign cùng lúc, hình sẽ rất dài. "
              f"Cân nhắc truyền `campaigns=[...]` để giới hạn lại.")
 
    fig, axes = _facet_grid_axes(len(campaigns))
    for i, c in enumerate(campaigns):
        sub = valid[valid["campaign"] == c]["rel_diff_pct"].dropna()
        _draw_rel_diff_hist(axes[i], sub, bins, config.THRESHOLD_PCT)
        axes[i].set_title(f"{c}\n(n={len(sub)})", fontsize=9)
        axes[i].set_xlabel("rel_diff_pct (%)")
 
    fig.suptitle(f"Phân bố sai số tương đối theo Campaign — metric: {metric} (ngưỡng ±{config.THRESHOLD_PCT}%)")
    plt.tight_layout()
    plt.show()
 
 
def plot_rel_diff_ecdf(detail: pd.DataFrame, metrics: list[str] | None = None) -> pd.DataFrame:
    """ECDF của |rel_diff_pct| — trả lời trực tiếp câu "bao nhiêu % cohort có sai
    số <= X%?". Đường đỏ chấm đứng = ngưỡng THRESHOLD_PCT; giao điểm với mỗi
    đường ECDF chính là % đạt ngưỡng của metric đó (cũng in ra dạng bảng số).
    """
    metrics = metrics or ["ROAS_D0", "ROAS_D7", "ROAS_D28", "REVENUE_D0"]
    valid = _valid(detail)
 
    fig, ax = plt.subplots(figsize=(9, 5.5))
    _add_grid(ax)
    pct_within_rows = []
    for m in metrics:
        sub = valid[valid["metric"] == m]["rel_diff_pct"].abs().dropna().sort_values()
        if len(sub) == 0:
            continue
        y = np.arange(1, len(sub) + 1) / len(sub) * 100
        ax.plot(sub, y, marker=".", markersize=3, linewidth=1.5, label=m)
        pct_within = (sub <= config.THRESHOLD_PCT).mean() * 100
        pct_within_rows.append({"metric": m, "n": len(sub), "pct_within_threshold": round(pct_within, 1)})
 
    ax.axvline(config.THRESHOLD_PCT, color="red", linestyle=":", linewidth=1.5,
               label=f"Ngưỡng {config.THRESHOLD_PCT}%")
    ax.set_xlabel("|rel_diff_pct| (%)")
    ax.set_ylabel("% cohort có sai số <= giá trị này")
    ax.set_title("ECDF — Phân bố tích luỹ sai số tương đối")
    ax.set_ylim(0, 100)
    ax.legend(fontsize=8)
    plt.tight_layout()
    plt.show()
 
    pct_within_df = pd.DataFrame(pct_within_rows)
    print("=== % cohort đạt ngưỡng (|rel_diff_pct| <= THRESHOLD_PCT) ===")
    print(pct_within_df.to_string(index=False))
    return pct_within_df
 