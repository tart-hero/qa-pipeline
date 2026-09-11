# QA Pipeline — Reconciliation Metabase vs Adjust

Đối chiếu ROAS/Cost/Install tự tính (BigQuery, qua Metabase) với số liệu benchmark trên Adjust,
qua API — không dùng CSV thủ công.

## Cấu trúc

```
qa-pipeline/
├── config.py              # TẤT CẢ hằng số nghiệp vụ + đọc .env — sửa ở đây khi đổi threshold/card_id
├── clients/                # Gọi API thuần tuý (Metabase, Adjust) — không chứa logic nghiệp vụ
├── reconciliation/         # Logic normalize / merge / flag / summary — không phụ thuộc HTTP
├── notebooks/QA.ipynb      # Chỉ orchestration + hiển thị, import từ 2 package trên
├── tests/                  # Unit test logic, không gọi API thật
└── docs/reconciliation.md  # Tài liệu sống — lịch sử debug, quyết định đã chốt
```

## Setup lần đầu

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env            # rồi điền giá trị thật vào .env
```

Trong VSCode: mở `notebooks/QA.ipynb`, chọn kernel đúng `venv` vừa tạo (góc trên phải notebook).

## Chạy

Mở `notebooks/QA.ipynb`, Run All. Kết quả in ra % discrepancy theo từng mốc ROAS D0-D28,
kèm chi tiết các dòng bị flag "Discrepancy".

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
  Metabase mart tính Ad-only revenue (IAA), không phải Total.
- `reattributed=false` — khớp filter UI "Attribution status: Installed". Thiếu param này từng gây
  ROAS lệch gần gấp đôi.
- `ad_spend_mode=network` — đã xác nhận Cost khớp 100% với mart.
- Network mapping `ALV` (Adjust) ↔ `APPLOVIN` (Metabase) — 2 convention đặt tên khác nhau theo
  thiết kế, không phải lỗi dữ liệu.
- Campaign key KHÔNG normalize — tên campaign đã xác nhận khớp nguyên văn giữa 2 nguồn.

## Mở rộng sang Game B (iOS)

1. Thêm `ADJUST_APP_TOKEN_CDS_IOS` vào `.env`
2. Thêm `METABASE_CARD_ID_CDS_IOS` và `ADJUST_APP_TOKEN_CDS_IOS` vào `config.py`
3. Copy `notebooks/QA.ipynb` thành `notebooks/QA_GameB_iOS.ipynb`, đổi các biến tương ứng —
   toàn bộ `clients/` và `reconciliation/` dùng lại nguyên vẹn, không cần sửa.
