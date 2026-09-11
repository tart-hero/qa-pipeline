"""
SỬA FILE NÀY MỖI LẦN CHẠY — đây là nơi DUY NHẤT cần chỉnh.
Không sửa config.py (đó là registry tĩnh) hay notebook (đó là orchestration).
"""

# 1 trong: "game_a_android", "game_b_ios", "game_c_android", "game_c_ios"
# (xem đầy đủ danh sách + nhãn tại config.GAMES)
GAME_KEY = "game_a_android"

# Khoảng ngày đối chiếu — chỉ sửa Ở ĐÂY, notebook sẽ tự format đúng cho cả
# Metabase (dùng dấu ~) và Adjust (dùng dấu :), không còn 2 chỗ lệch nhau.
DATE_PERIOD_START = "2026-07-19"
DATE_PERIOD_END = "2026-09-06"

# Ngày biết trước là lỗi/thiếu dữ liệu, cần loại khỏi lần chạy này.
# VD: EXCLUDED_DATES = ["2026-08-05", "2026-08-06"]
EXCLUDED_DATES: list[str] = ["2026-09-05"]

# Mốc "hôm nay" dùng để tính Cohort Age (xem config.py mục Reconciliation).
# None -> tự dùng ngày hệ thống hiện tại (phù hợp chạy thường ngày).
# Đặt tường minh (VD "2026-08-12") khi muốn tái lập đúng 1 lần chạy trong quá khứ.
DATA_ASOF_DATE = "2026-09-06"