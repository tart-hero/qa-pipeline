"""
SỬA FILE NÀY MỖI LẦN CHẠY — đây là nơi DUY NHẤT cần chỉnh.
Không sửa config.py (đó là registry tĩnh) hay notebook (đó là orchestration).
"""
from config import NETWORK_OPTIONS as CONFIG_NETWORKS

# 1 trong: "game_a_android", "game_b_ios", "game_c_android", "game_c_ios"
# (xem đầy đủ danh sách + nhãn tại config.GAMES)
GAME_KEY = "game_a_android"

# Network cho lần chạy này — 1 trong các key của config.NETWORK_OPTIONS:
# list(CONFIG_NETWORKS.keys())  # → ['applovin', 'unity']
# - str (1 key)      -> chỉ lấy đúng 1 network đó, cho cả Metabase lẫn Adjust.
# - list ĐỦ CẢ 2 key -> gộp CẢ 2 network vào CHUNG 1 df_mb + 1 df_adjust
#                       (Metabase bỏ trống filter "network", tự trả cả 2 vì
#                       SQL card_id=81 đã hardcode WHERE network IN (...);
#                       Adjust dùng network__in="ALV,Unity"). Không cần chạy
#                       notebook riêng từng network rồi tự ghép.
# NETWORK_KEY = "applovin"  # Chạy riêng AppLovin
# NETWORK_KEY = "unity"                 # Chạy riêng Unity
NETWORK_KEY = ["applovin", "unity"]   # Chạy gộp cả 2 network

# Khoảng ngày đối chiếu — chỉ sửa Ở ĐÂY, notebook sẽ tự format đúng cho cả
# Metabase (dùng dấu ~) và Adjust (dùng dấu :), không còn 2 chỗ lệch nhau.
DATE_PERIOD_START = "2026-08-05"
DATE_PERIOD_END = "2026-09-27"

# Ngày biết trước là lỗi/thiếu dữ liệu, cần loại khỏi lần chạy này.
# VD: EXCLUDED_DATES = ["2026-08-05", "2026-08-06"]
EXCLUDED_DATES: list[str] = []

# Mốc "hôm nay" dùng để tính Cohort Age (xem config.py mục Reconciliation).
# None -> tự dùng ngày hệ thống hiện tại (phù hợp chạy thường ngày).
# Đặt tường minh (VD "2026-08-12") khi muốn tái lập đúng 1 lần chạy trong quá khứ.
DATA_ASOF_DATE = "2026-09-27"