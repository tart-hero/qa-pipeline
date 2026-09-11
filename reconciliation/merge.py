"""Merge DataFrame Metabase và Adjust đã normalize, theo key (date, network_key, campaign_key)."""
import pandas as pd


def merge_sources(mb_norm: pd.DataFrame, adj_norm: pd.DataFrame) -> pd.DataFrame:
    """Outer join + cột `_merge` để biết rõ dòng nào chỉ có ở 1 bên
    (dấu hiệu lệch join key — campaign đổi tên, network thiếu mapping...)."""
    return mb_norm.merge(
        adj_norm,
        on=["date", "network_key", "campaign_key"],
        how="outer",
        suffixes=("_mb", "_adj"),
        indicator=True,
    )


def report_join_gaps(merged: pd.DataFrame) -> dict:
    """In ra và trả về thống kê các dòng không khớp được join key ở cả 2 phía.
    Luôn gọi hàm này TRƯỚC khi lọc `both` — đừng âm thầm bỏ qua phần lệch."""
    only_mb = merged[merged["_merge"] == "left_only"]
    only_adj = merged[merged["_merge"] == "right_only"]
    both_count = int((merged["_merge"] == "both").sum())

    print(f"Khớp cả 2 nguồn: {both_count} dòng")
    print(f"Chỉ có ở Metabase: {len(only_mb)} dòng")
    print(f"Chỉ có ở Adjust: {len(only_adj)} dòng")

    if len(only_mb) > 0:
        print("\n⚠️ Chỉ có ở Metabase:")
        print(only_mb[["date", "Campaign", "Network"]].drop_duplicates())

    if len(only_adj) > 0:
        print("\n⚠️ Chỉ có ở Adjust:")
        print(only_adj[["date", "campaign_network", "network"]].drop_duplicates())

    return {"both": both_count, "only_mb": len(only_mb), "only_adj": len(only_adj)}
