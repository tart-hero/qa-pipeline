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

# card_id của Question "Cohort ROAS + Revenue by Campain" (CDS Android)
# Xác nhận qua qa_explore.ipynb — Question này KHÔNG nằm trong Dashboard,
# nó là 1 Native SQL Question độc lập có các filter riêng.
METABASE_CARD_ID_CDS_ANDROID = 81

# ---------------------------------------------------------------------------
# Adjust
# ---------------------------------------------------------------------------
ADJUST_API_TOKEN = _require_env("ADJUST_API_TOKEN")
ADJUST_APP_TOKEN_CDS_ANDROID = _require_env("ADJUST_APP_TOKEN_CDS_ANDROID")

ROAS_DAYS = ["d0", "d3", "d7", "d14", "d28"]

# Đã xác nhận qua đối chiếu Revenue thô: Metabase mart tính Ad-only revenue (IAA),
# nên dùng "roas_ad_cal"/"ad_revenue_total_cal" (KHÔNG dùng "roas_cal"/"all_revenue_total_cal"
# — 2 biến thể đó là Total = IAA+IAP, sai phạm vi so sánh).
ROAS_METRIC_PREFIX = "roas_ad_cal"
REVENUE_METRIC_PREFIX = "ad_revenue_total_cal"

# Danh sách metric cần fetch từ Adjust — đủ cho cả ROAS, Revenue, Cost, Installs.
ADJUST_METRICS_CDS_ANDROID = (
    ["installs", "network_cost"]
    + [f"{ROAS_METRIC_PREFIX}_{d}" for d in ROAS_DAYS]
    + [f"{REVENUE_METRIC_PREFIX}_{d}" for d in ROAS_DAYS]
)

# Các param filter Adjust đã xác nhận khớp đúng với Template dashboard
# và với số liệu Metabase (xem lịch sử debug trong docs/reconciliation.md):
#   - cohort_maturity=mature   : Adjust trả 0/NULL cho cohort chưa mature thay vì
#                                 carry-forward, giảm bớt (không thay thế hoàn toàn)
#                                 nhu cầu tự tính Cohort Age phía dưới
#   - ad_spend_mode=network    : khớp Cost 100% với mart (không dùng "mixed")
#   - reattributed=false       : khớp filter UI "Attribution status: Installed"
#     -> đây là nguyên nhân chính từng gây lệch ROAS gần gấp đôi khi bỏ sót
#   - ad_revenue_sources       : giới hạn đúng nguồn AppLovin MAX, khớp UI dashboard
ADJUST_EXTRA_PARAMS_CDS_ANDROID = {
    "cohort_maturity": "mature",
    "ad_spend_mode": "network",
    "network__in": "ALV",
    "ad_revenue_sources": "AppLovin Max",
    "reattributed": "false",
}

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
DATA_ASOF_DATE = "2026-09-06"  # VD: "2026-09-06"

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
