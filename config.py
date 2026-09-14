"""
Cấu hình chung cho toàn bộ pipeline QA (Metabase <-> Adjust reconciliation).

File này là NƠI DUY NHẤT chứa các hằng số nghiệp vụ / bí mật.
Khi cần đổi threshold, đổi card_id, thêm app mới... chỉ sửa ở đây,
không sửa rải rác trong clients/ hay notebook.
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _require_env(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(
            f"Thiếu biến môi trường '{key}'. Kiểm tra lại file .env "
            f"(xem .env.example để biết danh sách đầy đủ)."
        )
    return value


# ---------------------------------------------------------------------------
# Metabase
# ---------------------------------------------------------------------------
METABASE_URL = _require_env("METABASE_URL")
METABASE_API_KEY = _require_env("METABASE_API_KEY")

# ---------------------------------------------------------------------------
# Adjust
# ---------------------------------------------------------------------------
ADJUST_API_TOKEN = _require_env("ADJUST_API_TOKEN")

ROAS_DAYS = ["d0", "d3", "d7", "d14", "d28"]

# [CẬP NHẬT] Metabase mart giờ đã gồm cả IAP (không còn chỉ Ad-only/IAA), nên
# phạm vi Revenue/ROAS cần so là "total" (IAA+IAP) bên Adjust, KHÔNG phải
# "ad_only" (chỉ IAA) như quyết định ban đầu (xem lịch sử trong docs/reconciliation.md).
# 2 bộ prefix tương ứng 2 phạm vi — chọn qua "revenue_scope" trong GAMES[...] bên dưới,
# để game nào có mart CHƯA gồm IAP vẫn dùng lại "ad_only" mà không cần sửa code ở đây.
_REVENUE_SCOPE_PREFIXES = {
    "ad_only": {"roas": "roas_ad_cal", "revenue": "ad_revenue_total_cal"},
    "total": {"roas": "roas_cal", "revenue": "all_revenue_total_cal"},
}

# Param filter Adjust mặc định — áp dụng cho mọi game trừ khi override riêng
# trong GAMES[...]["adjust_extra_params"] bên dưới. Xem docs/reconciliation.md
# để biết lý do chọn từng param (đã xác nhận qua debug thực tế với Game A):
#   - cohort_maturity=mature : Adjust trả 0/NULL cho cohort chưa mature thay vì
#                               carry-forward
#   - ad_spend_mode=network  : khớp Cost 100% với mart (Game A)
#   - reattributed=false     : khớp filter UI "Attribution status: Installed" —
#                               thiếu param này từng gây ROAS lệch gần gấp đôi
_ADJUST_EXTRA_PARAMS_DEFAULT = {
    "cohort_maturity": "mature",
    "ad_spend_mode": "network",
    "reattributed": "false",
}

# ---------------------------------------------------------------------------
# Registry 4 game — THÊM/SỬA game ở đây khi cần, KHÔNG sửa ở notebook.
# Chọn game nào chạy cho lần này -> sửa trong run_config.py (không sửa file này).
# ---------------------------------------------------------------------------
GAMES = {
    "game_a_android": {
        "label": "Game A (CDS) — Android",
        "adjust_app_token_env": "ADJUST_APP_TOKEN_CDS_ANDROID",
        # card_id của Question "Cohort ROAS + Revenue by Campain" — Native SQL
        # Question độc lập (không nằm trong Dashboard), đã xác nhận qua qa_explore.ipynb.
        "metabase_card_id": 81,
        "metabase_game": ["Game A"],
        "metabase_platform": ["ANDROID"],
        # [CẬP NHẬT] Mart đã gồm IAP -> so Total (roas_cal/all_revenue_total_cal).
        "revenue_scope": "ad_only",
        "adjust_extra_params": {
            **_ADJUST_EXTRA_PARAMS_DEFAULT,
            "network__in": "ALV",
            "ad_revenue_sources": "AppLovin Max",
        },
    },
    "game_b_ios": {
        "label": "Game B (CDS) — iOS",
        "adjust_app_token_env": "ADJUST_APP_TOKEN_CDS_IOS",
        # TODO: xác nhận lại card_id đúng cho Game B iOS — tạm dùng chung Question
        # 81 nếu mart/Question phục vụ chung nhiều game qua filter {{game}}/{{platform}}.
        # Nếu Game B có Question riêng, đổi số này.
        "metabase_card_id": 81,
        "metabase_game": ["Game B"],
        "metabase_platform": ["IOS"],
        # TODO: xác nhận lại "total" có đúng cho Game B không — tạm theo Game A.
        "revenue_scope": "ad_only",
        # TODO: xác nhận lại network__in/ad_revenue_sources cho Game B — tạm copy
        # theo Game A, CHƯA được verify qua đối chiếu thực tế như Game A.
        "adjust_extra_params": {
            **_ADJUST_EXTRA_PARAMS_DEFAULT,
            "network__in": "ALV",
            "ad_revenue_sources": "AppLovin Max",
        },
    },
    "game_c_android": {
        "label": "Game C (BCE) — Android",
        "adjust_app_token_env": "ADJUST_APP_TOKEN_BCE_ANDROID",
        # TODO: xác nhận card_id đúng cho Game C — Game C có thể không dùng chung
        # mart/Question với Game A/B (tên game khác "CDS"), CẦN kiểm tra lại.
        "metabase_card_id": 81,
        "metabase_game": ["Game C"],
        "metabase_platform": ["ANDROID"],
        # TODO: xác nhận lại "total" có đúng cho Game C không.
        "revenue_scope": "ad_only",
        "adjust_extra_params": {
            **_ADJUST_EXTRA_PARAMS_DEFAULT,
            "network__in": "ALV",
            "ad_revenue_sources": "AppLovin Max",
        },
    },
    "game_c_ios": {
        "label": "Game C (BCE) — iOS",
        "adjust_app_token_env": "ADJUST_APP_TOKEN_BCE_IOS",
        "metabase_card_id": 81,  # TODO: xác nhận lại, xem ghi chú ở game_c_android
        "metabase_game": ["Game C"],
        "metabase_platform": ["IOS"],
        # TODO: xác nhận lại "total" có đúng cho Game C không.
        "revenue_scope": "ad_only",
        "adjust_extra_params": {
            **_ADJUST_EXTRA_PARAMS_DEFAULT,
            "network__in": "ALV",
            "ad_revenue_sources": "AppLovin Max",
        },
    },
}


def get_adjust_app_token(game_key: str) -> str:
    """Đọc token đúng game từ .env — chỉ đọc khi thực sự cần (lazy), để không bắt
    buộc phải khai báo đủ token của cả 4 game nếu 1 lần chạy chỉ dùng 1 game."""
    if game_key not in GAMES:
        raise KeyError(f"game_key '{game_key}' không tồn tại trong config.GAMES. "
                        f"Các game hợp lệ: {list(GAMES.keys())}")
    env_key = GAMES[game_key]["adjust_app_token_env"]
    return _require_env(env_key)

# ---------------------------------------------------------------------------
# Reconciliation / flagging
# ---------------------------------------------------------------------------
# [CHỐT] Sai số tương đối (ratio = mb/adj) dùng THỐNG NHẤT cho MỌI metric —
# đã đánh giá và revert khỏi cách tính absolute-diff threshold trước đó.
# Ngưỡng theo lưu ý trong tài liệu dự án gốc (~5% tương đối).
THRESHOLD_PCT = 5.0

# metric_name -> (tên cột bên Metabase, tên cột/metric bên Adjust) — PHỤ THUỘC
# revenue_scope của từng game, nên chuyển thành hàm thay vì hằng số cố định.
# Các cột Metabase lấy nguyên từ output của card_id=81 (đã là số, KHÔNG cần
# clean_money/clean_pct như khi đọc CSV — đây là điểm khác biệt so với notebook
# tham khảo QA_GameA_Android_ALV.ipynb vốn đọc từ file CSV export thủ công).
def get_metric_map(game_key: str) -> dict:
    scope = GAMES[game_key].get("revenue_scope", "total")
    prefixes = _REVENUE_SCOPE_PREFIXES[scope]
    roas_prefix, revenue_prefix = prefixes["roas"], prefixes["revenue"]

    metric_map = {
        f"ROAS_D{d[1:]}": (f"ROAS D{d[1:]}", f"{roas_prefix}_{d}") for d in ROAS_DAYS
    }
    metric_map["COST"] = ("Cost", "network_cost")
    metric_map["INSTALLS"] = ("Adjust Installs", "installs")
    for d in ROAS_DAYS:
        metric_map[f"REVENUE_D{d[1:]}"] = (f"Revenue D{d[1:]}", f"{revenue_prefix}_{d}")
    return metric_map


def get_adjust_metrics(game_key: str) -> list[str]:
    """Danh sách metric cần fetch từ Adjust — đúng theo revenue_scope của game đó."""
    scope = GAMES[game_key].get("revenue_scope", "total")
    prefixes = _REVENUE_SCOPE_PREFIXES[scope]
    return (
        ["installs", "network_cost"]
        + [f"{prefixes['roas']}_{d}" for d in ROAS_DAYS]
        + [f"{prefixes['revenue']}_{d}" for d in ROAS_DAYS]
    )


METRIC_ORDER = [
    "ROAS_D0", "ROAS_D3", "ROAS_D7", "ROAS_D14", "ROAS_D28",
    "REVENUE_D0", "REVENUE_D3", "REVENUE_D7", "REVENUE_D14", "REVENUE_D28",
    "COST", "INSTALLS",
]

# Chỉ ROAS_DX và REVENUE_DX có khái niệm "maturity" (COST/INSTALLS thì không).
# KHÔNG phụ thuộc revenue_scope — số ngày yêu cầu cho từng mốc DX là cố định,
# chỉ nguồn cột Adjust đổi theo scope, không phải yêu cầu về "tuổi" cohort.
ROAS_DAY_MAP = {f"ROAS_D{d[1:]}": int(d[1:]) for d in ROAS_DAYS}
REVENUE_DAY_MAP = {f"REVENUE_D{d[1:]}": int(d[1:]) for d in ROAS_DAYS}
MATURITY_DAY_MAP = {**ROAS_DAY_MAP, **REVENUE_DAY_MAP}

# Mốc "hôm nay" dùng để tính Cohort Age = DATA_ASOF_DATE - Cohort Date.
# Để None -> tự lấy ngày hệ thống hiện tại. Đặt tường minh khi bạn muốn tái
# lập lại đúng 1 lần chạy trong quá khứ (VD đối chiếu lại số liệu của 1 ngày cũ).
DATA_ASOF_DATE = None  # VD: "2026-09-06"

# True  -> tự động loại các ROAS_DX/REVENUE_DX mà cohort chưa đủ X ngày tuổi
#          (tính theo Cohort Age) khỏi so sánh — tránh so sánh sai vì Adjust
#          Dashboard có thể carry-forward giá trị cũ cho cohort chưa mature.
# False -> quay về logic cũ, chỉ dựa vào NaN/không NaN ở 2 phía.
EXCLUDE_IMMATURE_COHORTS = True

# Danh sách ngày biết trước là lỗi/thiếu dữ liệu, cần loại khỏi lần chạy này.
# Đây là kiến thức riêng theo từng lần chạy (không cố định lâu dài) — cân nhắc
# override trực tiếp trong notebook thay vì sửa ở đây nếu chỉ dùng 1 lần.
EXCLUDED_DATES: list[str] = []

# Mapping tên network giữa 2 nguồn — Adjust dùng viết tắt (ALV), Metabase dùng
# tên đầy đủ (APPLOVIN) vì mart BigQuery lưu theo convention riêng.
# QUAN TRỌNG: khi thêm Unity/GGA vào scope, bổ sung dòng tương ứng ở đây,
# và kiểm tra lại giá trị "network" thật Adjust trả về trước khi thêm
# (dùng cell dò giá trị trong notebook, đừng đoán).
NETWORK_NAME_MAPPING = {
    "ALV": "APPLOVIN",
    "APPLOVIN": "APPLOVIN",
    "UNITY": "UNITY",
    "GGA": "GOOGLE ADS",
    "GOOGLE ADS": "GOOGLE ADS",
}