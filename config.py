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

# Đã xác nhận qua đối chiếu Revenue thô: Metabase mart tính Ad-only revenue (IAA),
# nên dùng "roas_ad_cal"/"ad_revenue_total_cal" (KHÔNG dùng "roas_cal"/"all_revenue_total_cal"
# — 2 biến thể đó là Total = IAA+IAP, sai phạm vi so sánh). Giống nhau cho mọi game.
ROAS_METRIC_PREFIX = "roas_ad_cal"
REVENUE_METRIC_PREFIX = "ad_revenue_total_cal"

# Danh sách metric cần fetch từ Adjust — đủ cho cả ROAS, Revenue, Cost, Installs.
# Giống nhau cho mọi game (chỉ app_token và extra_params khác nhau theo game).
ADJUST_METRICS = (
    ["installs", "network_cost"]
    + [f"{ROAS_METRIC_PREFIX}_{d}" for d in ROAS_DAYS]
    + [f"{REVENUE_METRIC_PREFIX}_{d}" for d in ROAS_DAYS]
)

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

# metric_name -> (tên cột bên Metabase, tên cột/metric bên Adjust)
# Các cột Metabase lấy nguyên từ output của card_id=81 (đã là số, KHÔNG cần
# clean_money/clean_pct như khi đọc CSV — đây là điểm khác biệt so với notebook
# tham khảo QA_GameA_Android_ALV.ipynb vốn đọc từ file CSV export thủ công).
METRIC_MAP = {
    "ROAS_D0":  ("ROAS D0",  f"{ROAS_METRIC_PREFIX}_d0"),
    "ROAS_D3":  ("ROAS D3",  f"{ROAS_METRIC_PREFIX}_d3"),
    "ROAS_D7":  ("ROAS D7",  f"{ROAS_METRIC_PREFIX}_d7"),
    "ROAS_D14": ("ROAS D14", f"{ROAS_METRIC_PREFIX}_d14"),
    "ROAS_D28": ("ROAS D28", f"{ROAS_METRIC_PREFIX}_d28"),
    "COST":     ("Cost", "network_cost"),
    "INSTALLS": ("Adjust Installs", "installs"),
    "REVENUE_D0":  ("Revenue D0",  f"{REVENUE_METRIC_PREFIX}_d0"),
    "REVENUE_D3":  ("Revenue D3",  f"{REVENUE_METRIC_PREFIX}_d3"),
    "REVENUE_D7":  ("Revenue D7",  f"{REVENUE_METRIC_PREFIX}_d7"),
    "REVENUE_D14": ("Revenue D14", f"{REVENUE_METRIC_PREFIX}_d14"),
    "REVENUE_D28": ("Revenue D28", f"{REVENUE_METRIC_PREFIX}_d28"),
}

METRIC_ORDER = [
    "ROAS_D0", "ROAS_D3", "ROAS_D7", "ROAS_D14", "ROAS_D28",
    "REVENUE_D0", "REVENUE_D3", "REVENUE_D7", "REVENUE_D14", "REVENUE_D28",
    "COST", "INSTALLS",
]

# Chỉ ROAS_DX và REVENUE_DX có khái niệm "maturity" (COST/INSTALLS thì không).
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