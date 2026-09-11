# Reconciliation — Metabase vs Adjust (CDS Android)

## Nguồn dữ liệu

- **Metabase**: Question `card_id=81` ("Cohort ROAS + Revenue by Campain"), Native SQL Question
  độc lập (không nằm trong Dashboard), query trực tiếp mart
  `iec-data-game-dev.mart.dashboard_cohort_roas_daily`, đã filter cứng `network = 'APPLOVIN'`.
- **Adjust**: JSON Report endpoint (`/reports-service/report`), app token CDS Android.

## Threshold flagging

- Metric: `ratio = mb/adj` cho scope chung; riêng ROAS dùng **absolute diff (percentage point)**,
  ngưỡng `ROAS_THRESHOLD_ABS_PP = 0.05` (xem `config.py`).
- Flag: `OK` / `Discrepancy` / `Missing` (NaN — cohort chưa mature ở 1 trong 2 bên).

## Lịch sử debug — vì sao các param Adjust được chọn như hiện tại

| Vấn đề quan sát | Nguyên nhân | Cách xử lý |
|---|---|---|
| `network_key` dtype `float64` khi merge | `.apply()` trên cột network chưa ép `.astype(str)` tường minh, lộ ra khi 1 DataFrame gần rỗng | Luôn `.astype(str)` sau `.apply(normalize_network)` |
| Adjust trả `network="ALV"`, Metabase trả `"APPLOVIN"` | 2 convention đặt tên khác nhau theo thiết kế (không phải lỗi format) | `NETWORK_NAME_MAPPING` trong `config.py` |
| Cost/Install khớp 100% nhưng ROAS D7 lệch gấp ~2 lần | Request Adjust không truyền `reattributed`, mặc định `all` (gộp cả reattributed users); UI dashboard đang filter `Attribution status: Installed` | Thêm `reattributed=false` |
| `filters_data` trả 400 cho `partner`/`reattributed` | 2 filter này không có value-list tra được qua endpoint `filters_data` (khác với `ad_revenue_sources`, `attribution_types`) — nhưng vẫn dùng được bình thường như filter của report chính | Không tra qua `filters_data`, dùng thẳng giá trị đã biết từ UI |
| ROAS lệch 30-52% (Game B, trước đó) | Nhầm cột `roas_cal_dX` (Total = IAA+IAP) với `roas_ad_cal_dX` (Ad-only) | Xác nhận đúng cột qua đối chiếu Revenue thô (`ad_revenue_total_cal_dX` vs `Revenue DX` bên Metabase), chốt `ROAS_METRIC_PREFIX="roas_ad_cal"` |

## Chưa xác nhận / cần theo dõi tiếp

- **Match loss (`No_ID`)**: nếu sau khi đã fix `reattributed`, vẫn còn discrepancy dư (không còn
  gấp đôi nhưng vẫn > threshold), nghi vấn tiếp theo là tỷ lệ thất thoát khi match device ID giữa
  MAX user-level revenue và Adjust install (AppLovin user-level coverage ước tính ~87% impression /
  ~95% revenue theo tài liệu gốc dự án — chưa verify chính thức).
- **BLDROAS install mismatch**: campaign `260406` (Android) có install mismatch nhất quán —
  chưa rõ nguyên nhân, cần điều tra riêng ở tầng cấu hình campaign.
