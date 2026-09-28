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
# [CẬP NHẬT v4 — SQL card_id=81 đổi từ Field Filter sang Plain Variable]
# game/platform giờ là SCALAR STRING (không phải list) vì SQL dùng so sánh
# `full_name = {{game}}` (plain variable, single-value) thay vì Field Filter
# đa chọn như trước. "network__in" KHÔNG còn cố định trong từng game nữa — xem
# NETWORK_OPTIONS + get_adjust_extra_params() bên dưới: network giờ là lựa chọn
# CHUNG cho lần chạy (qua run_config.NETWORK_KEY), áp dụng cho CẢ Metabase lẫn
# Adjust cùng lúc, vì 2 phía phải lọc cùng 1 network mới join được.
# "revenue_scope" không còn cần thiết — SQL giờ LUÔN tính ROAS = ad + IAP.
# ---------------------------------------------------------------------------
GAMES = {
    "game_a_android": {
        "label": "Game A (CDS) — Android",
        "adjust_app_token_env": "ADJUST_APP_TOKEN_CDS_ANDROID",
        "metabase_card_id": 81,
        "metabase_game": "Game A",
        "metabase_platform": "ANDROID",
        "adjust_extra_params": dict(_ADJUST_EXTRA_PARAMS_DEFAULT, ad_revenue_sources="AppLovin Max"),
    },
    "game_b_ios": {
        "label": "Game B (CDS) — iOS",
        "adjust_app_token_env": "ADJUST_APP_TOKEN_CDS_IOS",
        # TODO: xác nhận lại card_id đúng cho Game B iOS nếu có Question riêng.
        "metabase_card_id": 81,
        "metabase_game": "Game B",
        "metabase_platform": "IOS",
        # TODO: xác nhận lại ad_revenue_sources cho Game B — tạm copy theo Game A.
        "adjust_extra_params": dict(_ADJUST_EXTRA_PARAMS_DEFAULT, ad_revenue_sources="AppLovin Max"),
    },
    "game_c_android": {
        "label": "Game C (BCE) — Android",
        "adjust_app_token_env": "ADJUST_APP_TOKEN_BCE_ANDROID",
        # TODO: xác nhận card_id đúng cho Game C — có thể không dùng chung mart/Question.
        "metabase_card_id": 81,
        "metabase_game": "Game C",
        "metabase_platform": "ANDROID",
        "adjust_extra_params": dict(_ADJUST_EXTRA_PARAMS_DEFAULT, ad_revenue_sources="AppLovin Max"),
    },
    "game_c_ios": {
        "label": "Game C (BCE) — iOS",
        "adjust_app_token_env": "ADJUST_APP_TOKEN_BCE_IOS",
        "metabase_card_id": 81,  # TODO: xác nhận lại, xem ghi chú ở game_c_android
        "metabase_game": "Game C",
        "metabase_platform": "IOS",
        "adjust_extra_params": dict(_ADJUST_EXTRA_PARAMS_DEFAULT, ad_revenue_sources="AppLovin Max"),
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
# [MỚI] Lựa chọn Network — dùng CHUNG cho cả Metabase lẫn Adjust trong 1 lần
# chạy (chọn qua run_config.NETWORK_KEY).
# 2 hệ đặt tên khác nhau: Metabase dùng tên đầy đủ viết hoa (khớp literal trong
# SQL), Adjust dùng viết tắt — ĐÃ xác nhận qua response thật trước đó
# (network="ALV" cho AppLovin, network="Unity" cho Unity — chú ý "Unity" viết
# hoa chữ đầu bên Adjust, KHÁC "UNITY" toàn hoa bên Metabase).
#
# [CẬP NHẬT 2026-09-26] Card Metabase id=81 đã được sửa lại phía owner
# (2026-09-24): "network" giờ là Field Filter multi-select THẬT (target
# ["dimension", ["template-tag", "network"]], isMultiSelect=true) — không còn
# là Plain Variable scalar như bản cũ, và view nguồn (`v_dashboard_cohort_roas`)
# giờ có CẢ network 'ORGANIC' (trước đây SQL hardcode WHERE network IN
# ('APPLOVIN','UNITY') nên không cần lo Organic lọt vào). Vì vậy PHẢI luôn
# truyền filter "network" tường minh (dạng list) cho Metabase — bỏ trống sẽ
# lấy CẢ Organic, sai lệch với Adjust. Đã xác nhận qua request thật: value
# phải là list dù chỉ chọn 1 network (VD ["APPLOVIN"]), và có thể chọn bất kỳ
# tập con nào (không còn giới hạn "chỉ 1 hoặc đủ cả 2" như bản Plain Variable).
# ---------------------------------------------------------------------------
NETWORK_OPTIONS = {
    "applovin": {"metabase": "APPLOVIN", "adjust": "ALV"},
    "unity": {"metabase": "UNITY", "adjust": "Unity"},
}


def get_metabase_network_value(network_key) -> list[str]:
    """network_key: 1 key (str) hoặc list nhiều key.
    Luôn trả về LIST giá trị Metabase tương ứng (kể cả khi chỉ 1 network) —
    "network" trên card_id=81 giờ là Field Filter multi-select thật, PHẢI
    truyền value dạng list (xem comment ở NETWORK_OPTIONS)."""
    keys = [network_key] if isinstance(network_key, str) else list(network_key)
    invalid = [k for k in keys if k not in NETWORK_OPTIONS]
    if invalid:
        raise KeyError(f"network_key không hợp lệ: {invalid}. Chọn trong: {list(NETWORK_OPTIONS)}")
    return [NETWORK_OPTIONS[k]["metabase"] for k in keys]


def get_adjust_extra_params(game_key: str, network_key) -> dict:
    """Merge adjust_extra_params cố định của game với network__in được CHỌN TẠI
    RUNTIME (qua run_config.NETWORK_KEY) — bắt buộc để Metabase và Adjust luôn
    lọc cùng 1 tập network, nếu không sẽ ra 100% only_mb/only_adj khi merge
    (không join được dòng nào).

    network_key: 1 key (str) -> network__in = 1 giá trị Adjust tương ứng.
    list nhiều key (vd ["applovin", "unity"]) -> network__in = list nối bằng
    dấu phẩy (Adjust hỗ trợ multi-value cho *__in) — khớp với danh sách truyền
    cho get_metabase_network_value() ở trên."""
    if game_key not in GAMES:
        raise KeyError(f"game_key '{game_key}' không tồn tại trong config.GAMES.")
    params = dict(GAMES[game_key]["adjust_extra_params"])  # copy, không sửa bản gốc trong GAMES
    if isinstance(network_key, (list, tuple)):
        params["network__in"] = get_adjust_network_filter(list(network_key))
    else:
        if network_key not in NETWORK_OPTIONS:
            raise KeyError(f"network_key '{network_key}' không hợp lệ. Chọn 1 trong: {list(NETWORK_OPTIONS)}")
        params["network__in"] = NETWORK_OPTIONS[network_key]["adjust"]
    return params


# ---------------------------------------------------------------------------
# Reconciliation / flagging
# ---------------------------------------------------------------------------
# [CHỐT] Sai số tương đối (ratio = mb/adj) dùng THỐNG NHẤT cho MỌI metric —
# đã đánh giá và revert khỏi cách tính absolute-diff threshold trước đó.
# Ngưỡng theo lưu ý trong tài liệu dự án gốc (~5% tương đối).
THRESHOLD_PCT = 5.0

# [CẬP NHẬT v4] SQL card_id=81 giờ LUÔN tính ROAS = ad revenue + IAP (không còn
# nhánh Ad-only) — "revenue_scope" không còn ý nghĩa, bỏ khỏi hàm này. Đồng thời
# Metabase giờ xuất 2 cột Revenue TÁCH RIÊNG (không còn 1 cột "Revenue DX" gộp):
#   - ad_revenue_total_cal_dX  (chỉ Ad revenue — IAA)
#   - revenue_total_cal_dX     (chỉ IAP)
# Metabase đặt tên cột TRÙNG THẲNG với tên metric Adjust tương ứng (theo comment
# trong SQL), nên metric_map dưới đây dùng chung 1 tên cho cả 2 vế.
# ⚠️ "revenue_total_cal_dX" là tên metric CHƯA được xác minh chính thức trong
# tài liệu công khai Adjust — kiểm tra trực tiếp bằng 1 request thử trước khi
# tin tưởng hoàn toàn (xem hướng dẫn kèm theo).
def get_metric_map(game_key: str) -> dict:
    metric_map = {
        f"ROAS_D{d[1:]}": (f"ROAS D{d[1:]}", f"roas_cal_{d}") for d in ROAS_DAYS
    }
    metric_map["COST"] = ("Cost", "network_cost")
    metric_map["INSTALLS"] = ("Adjust Installs", "installs")
    # [FIX] Metabase đặt tên cột TRÙNG với tên metric Adjust (theo thiết kế — xem
    # comment trong SQL card_id=81: "named exactly as the Adjust Report Service
    # API metrics they correspond to"). Sau merge_sources() (suffixes=("_mb","_adj")),
    # pandas TỰ ĐỘNG đổi tên các cột trùng này thành "..._mb"/"..._adj" — phải
    # tham chiếu đúng tên đã đổi, KHÔNG dùng tên gốc (tên gốc không còn tồn tại
    # trong `merged`, khiến build_detail() luôn ra NaN cho cả 2 vế -> 100% N/A,
    # dù cả 2 nguồn thực ra đều có dữ liệu).
    for d in ROAS_DAYS:
        metric_map[f"AD_REVENUE_D{d[1:]}"] = (f"ad_revenue_total_cal_{d}_mb", f"ad_revenue_total_cal_{d}_adj")
        metric_map[f"IAP_REVENUE_D{d[1:]}"] = (f"revenue_total_cal_{d}_mb", f"revenue_total_cal_{d}_adj")
    return metric_map


def get_adjust_metrics(game_key: str) -> list[str]:
    """Danh sách metric cần fetch từ Adjust — cố định cho mọi game (SQL giờ
    luôn dùng scope Total, không còn tuỳ biến theo game như trước)."""
    return (
        ["installs", "network_cost"]
        + [f"roas_cal_{d}" for d in ROAS_DAYS]
        + [f"ad_revenue_total_cal_{d}" for d in ROAS_DAYS]
        + [f"revenue_total_cal_{d}" for d in ROAS_DAYS]
    )


METRIC_ORDER = [
    "ROAS_D0", "ROAS_D3", "ROAS_D7", "ROAS_D14", "ROAS_D28",
    "AD_REVENUE_D0", "AD_REVENUE_D3", "AD_REVENUE_D7", "AD_REVENUE_D14", "AD_REVENUE_D28",
    "IAP_REVENUE_D0", "IAP_REVENUE_D3", "IAP_REVENUE_D7", "IAP_REVENUE_D14", "IAP_REVENUE_D28",
    "COST", "INSTALLS",
]

# Chỉ ROAS_DX/AD_REVENUE_DX/IAP_REVENUE_DX có khái niệm "maturity" (COST/INSTALLS thì không).
ROAS_DAY_MAP = {f"ROAS_D{d[1:]}": int(d[1:]) for d in ROAS_DAYS}
AD_REVENUE_DAY_MAP = {f"AD_REVENUE_D{d[1:]}": int(d[1:]) for d in ROAS_DAYS}
IAP_REVENUE_DAY_MAP = {f"IAP_REVENUE_D{d[1:]}": int(d[1:]) for d in ROAS_DAYS}
MATURITY_DAY_MAP = {**ROAS_DAY_MAP, **AD_REVENUE_DAY_MAP, **IAP_REVENUE_DAY_MAP}

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

def get_metabase_network_values(network_keys: list[str]) -> list[str]:
    """Convert list network_key → list metabase network values.
    
    VD: ['applovin', 'unity'] → ['APPLOVIN', 'UNITY']
    """
    if not network_keys:
        raise ValueError("network_keys không thể rỗng")
    return [NETWORK_OPTIONS[key]["metabase"] for key in network_keys]


def get_adjust_network_filter(network_keys: list[str]) -> str:
    """Convert list network_key → chuỗi filter cho Adjust network__in.
    
    VD: ['applovin', 'unity'] → 'ALV,Unity'
    (Adjust dùng dấu phẩy để ngăn cách trong query string)
    """
    if not network_keys:
        raise ValueError("network_keys không thể rỗng")
    return ",".join([NETWORK_OPTIONS[key]["adjust"] for key in network_keys])