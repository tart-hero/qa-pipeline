"""
Chuẩn hoá DataFrame Metabase và Adjust về cùng khoá join: (date, network_key, campaign_key).

Quyết định thiết kế (đã xác nhận qua thực nghiệm — xem docs/reconciliation.md):
- campaign_key: KHÔNG normalize (không .lower()/.strip()) — đã xác nhận tên
  campaign khớp nguyên văn giữa 2 nguồn, normalize thêm chỉ tăng rủi ro không
  cần thiết.
- network_key: BẮT BUỘC normalize qua NETWORK_NAME_MAPPING — Adjust dùng viết
  tắt (ALV), Metabase dùng tên đầy đủ (APPLOVIN), đây là 2 convention khác
  nhau theo thiết kế, không phải lỗi format.
"""
import pandas as pd

import config


def normalize_network(raw_value) -> str:
    """Map giá trị network thô về 1 giá trị chuẩn dùng để join.
    In cảnh báo (không raise) khi gặp giá trị lạ, để không chặn cả pipeline
    vì 1 network chưa kịp thêm vào mapping — nhưng vẫn hiện rõ để dễ phát hiện.
    """
    key = str(raw_value).strip().upper()
    if key not in config.NETWORK_NAME_MAPPING:
        print(f"⚠️ CẢNH BÁO: giá trị network lạ chưa có trong mapping: '{raw_value}' — cần bổ sung config.NETWORK_NAME_MAPPING")
        return key
    return config.NETWORK_NAME_MAPPING[key]


def normalize_metabase(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["date"] = pd.to_datetime(out["Cohort Date"]).dt.date
    out["campaign_key"] = out["Campaign"]
    out["network_key"] = out["Network"].apply(normalize_network).astype(str)
    return out


def normalize_adjust(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["date"] = pd.to_datetime(out["day"]).dt.date
    out["campaign_key"] = out["campaign_network"]
    out["network_key"] = out["network"].apply(normalize_network).astype(str)

    # Adjust trả metric dạng string — ép kiểu số, loại trừ tường minh network_key
    # để tránh bug dtype float64 khi .apply() gặp DataFrame rỗng.
    numeric_cols = [
        c for c in out.columns
        if c.startswith(("roas_", "network_", "installs", "ad_revenue_")) and c != "network_key"
    ]
    for c in numeric_cols:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def filter_excluded_dates(df: pd.DataFrame, excluded_dates: list[str], date_col: str = "date") -> pd.DataFrame:
    """Loại các ngày biết trước là lỗi/thiếu dữ liệu (config.EXCLUDED_DATES),
    gọi SAU khi đã normalize (cần cột 'date' kiểu date, không phải string)."""
    if not excluded_dates:
        return df
    excluded = {pd.to_datetime(d).date() for d in excluded_dates}
    before = len(df)
    out = df[~df[date_col].isin(excluded)].reset_index(drop=True)
    if before != len(out):
        print(f"Đã loại {before - len(out)} dòng thuộc các ngày bị exclude: {sorted(excluded)}")
    return out
