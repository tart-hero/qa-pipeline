# QA Pipeline — Reconciliation Metabase vs Adjust

Đối chiếu ROAS/Cost/Install/Revenue tự tính (BigQuery, qua Metabase) với số liệu benchmark trên
Adjust, qua API — không dùng CSV thủ công. Hỗ trợ 4 game/platform: Game A (Android), Game B (iOS),
Game C (Android + iOS).

## Cấu trúc

```
qa-pipeline/
├── run_config.py           # NƠI DUY NHẤT sửa mỗi lần chạy: chọn game, khoảng ngày, ngày loại trừ
├── config.py                # Registry TĨNH: game nào dùng token/card_id/filter nào — sửa khi
│                             #   thêm game mới hoặc đổi hằng số nghiệp vụ (threshold, mapping...)
├── clients/                 # Gọi API thuần tuý (Metabase, Adjust) — không chứa logic nghiệp vụ
├── reconciliation/          # Logic normalize / merge / flag / summary — không phụ thuộc HTTP
├── notebooks/QA.ipynb       # Chỉ orchestration + hiển thị, đọc run_config.py + config.py
├── tests/                   # Unit test logic, không gọi API thật
├── outputs/<game_key>/      # Kết quả CSV xuất ra, tự tách thư mục theo từng game
└── docs/reconciliation.md   # Tài liệu sống — lịch sử debug, quyết định đã chốt
```

## Setup lần đầu

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env            # rồi điền giá trị thật vào .env — cần đủ token cho từng game sẽ chạy
```

`.env` cần các biến (điền dần theo game bạn thực sự chạy, không bắt buộc đủ cả 4 ngay từ đầu
nhờ cơ chế đọc lazy trong `config.get_adjust_app_token()`):

```
METABASE_URL=...
METABASE_API_KEY=...
ADJUST_API_TOKEN=...
ADJUST_APP_TOKEN_CDS_ANDROID=...   # Game A — Android
ADJUST_APP_TOKEN_CDS_IOS=...       # Game B — iOS
ADJUST_APP_TOKEN_BCE_ANDROID=...   # Game C — Android
ADJUST_APP_TOKEN_BCE_IOS=...       # Game C — iOS
```

Trong VSCode: mở `notebooks/QA.ipynb`, chọn kernel đúng `venv` vừa tạo (góc trên phải notebook).

## Chạy — chỉ sửa `run_config.py`

```python
# run_config.py
GAME_KEY = "game_a_android"   # 1 trong 4 key trong config.GAMES
DATE_PERIOD_START = "2026-07-19"
DATE_PERIOD_END = "2026-09-06"
EXCLUDED_DATES = []           # VD: ["2026-08-05"]
DATA_ASOF_DATE = None         # None = dùng ngày hệ thống hiện tại
```

Sửa xong → **Restart kernel** → mở `notebooks/QA.ipynb` → **Run All**.

Kết quả in ra % discrepancy theo từng metric (ROAS D0-D28, Revenue D0-D28, Cost, Installs),
kèm bảng tổng hợp theo Campaign và top các dòng lệch nhiều nhất. File CSV xuất vào
`outputs/<game_key>/`, tự tách riêng không đè lên nhau giữa các game.

Đổi game → chỉ sửa `GAME_KEY` trong `run_config.py`, Restart kernel, Run All lại — không sửa gì
trong notebook hay `config.py`.

## Chạy test (không cần API thật)

```bash
pip install pytest
cd tests && pytest -v
```

## Các quyết định quan trọng đã chốt (xem chi tiết trong `docs/reconciliation.md`)

- **Sai số tương đối `ratio = mb/adj` dùng thống nhất cho MỌI metric** (ROAS, Revenue, Cost,
  Installs), ngưỡng `THRESHOLD_PCT = 5.0`%. Output dạng long-format (`build_detail()`), 1 dòng =
  1 cohort x 1 metric.
- **Cohort chưa đủ maturity bị loại khỏi so sánh dựa trên Cohort Age**, không chỉ dựa vào NaN —
  vì Adjust Dashboard có thể carry-forward giá trị cũ cho cohort chưa mature.
- `ROAS_METRIC_PREFIX = "roas_ad_cal"`, `REVENUE_METRIC_PREFIX = "ad_revenue_total_cal"` —
  Metabase mart tính Ad-only revenue (IAA), không phải Total. **Đã xác nhận cho Game A**, CHƯA
  verify cho Game B/C.
- `reattributed=false` — khớp filter UI "Attribution status: Installed". Thiếu param này từng gây
  ROAS lệch gần gấp đôi. **Đã xác nhận cho Game A**, CHƯA verify cho Game B/C.
- `ad_spend_mode=network` — đã xác nhận Cost khớp 100% với mart (Game A).
- Network mapping `ALV` (Adjust) ↔ `APPLOVIN` (Metabase) — 2 convention đặt tên khác nhau theo
  thiết kế, không phải lỗi dữ liệu.
- Campaign key KHÔNG normalize — tên campaign đã xác nhận khớp nguyên văn giữa 2 nguồn (Game A).

## Trạng thái xác nhận theo từng game (`config.GAMES`)

| game_key | metabase_card_id | network__in | Trạng thái |
|---|---|---|---|
| `game_a_android` | 81 | ALV | ✅ Đã verify đầy đủ qua debug thực tế |
| `game_b_ios` | 81 | ALV (TODO) | ⚠️ Tạm copy theo Game A, CHƯA verify |
| `game_c_android` | 81 | ALV (TODO) | ⚠️ Tạm copy theo Game A, CHƯA verify — Game C có thể dùng Question/mart khác |
| `game_c_ios` | 81 | ALV (TODO) | ⚠️ Tạm copy theo Game A, CHƯA verify |

Trước khi tin kết quả của Game B/C: xác nhận lại đúng `metabase_card_id` (Question Metabase
tương ứng) và giá trị `network` thật Adjust trả về (có Unity/GGA ngoài AppLovin không), cập nhật
trực tiếp vào `config.GAMES[...]`.

Khi nào có data Unity có thể thêm vào list network__in

## Thêm game thứ 5 trở đi

1. Thêm `ADJUST_APP_TOKEN_<GAME_MOI>` vào `.env`
2. Thêm 1 entry mới vào `config.GAMES` (copy cấu trúc 1 game hiện có, sửa `label`,
   `adjust_app_token_env`, `metabase_card_id`, `metabase_game`, `metabase_platform`,
   `adjust_extra_params`)
3. Đổi `GAME_KEY` trong `run_config.py` sang key mới, chạy như bình thường —
   `clients/`, `reconciliation/`, `notebooks/QA.ipynb` dùng lại nguyên vẹn, không sửa gì thêm.