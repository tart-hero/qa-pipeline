"""
Client gọi Adjust Report Service API (JSON report endpoint).

Chỉ chịu trách nhiệm GỌI API và trả về DataFrame thô — không chứa logic
nghiệp vụ (không tự áp threshold, không tự chọn ROAS_METRIC_PREFIX...).
Logic đó thuộc về package `reconciliation/`.
"""
import time
from typing import Optional

import pandas as pd
import requests

ADJUST_REPORT_URL = "https://automate.adjust.com/reports-service/report"
ADJUST_FILTERS_URL = "https://automate.adjust.com/reports-service/filters_data"


class AdjustClient:
    def __init__(self, api_token: str):
        self.headers = {"Authorization": f"Bearer {api_token}"}

    def fetch_report(
        self,
        app_token: str,
        dimensions: list[str],
        metrics: list[str],
        date_period: str,
        extra_params: Optional[dict] = None,
        max_retries: int = 3,
    ) -> tuple[pd.DataFrame, dict]:
        """
        Gọi JSON report endpoint, trả về (DataFrame các dòng, dict totals).

        Tự động retry khi gặp 429 (rate limit), backoff theo cấp số nhân.
        In rõ response body khi lỗi 400 để dễ debug (Adjust luôn trả message
        cụ thể tham số nào sai).
        """
        params = {
            "app_token__in": app_token,
            "dimensions": ",".join(dimensions),
            "metrics": ",".join(metrics),
            "date_period": date_period,
            "format_dates": "false",
            **(extra_params or {}),
        }

        for attempt in range(max_retries):
            resp = requests.get(ADJUST_REPORT_URL, headers=self.headers, params=params)

            if resp.status_code == 429:
                wait = 2 ** attempt
                time.sleep(wait)
                continue

            if resp.status_code == 400:
                # Luôn in body TRƯỚC khi raise — Adjust trả message rõ ràng,
                # đừng để lỗi trôi qua raise_for_status() rồi mất thông tin.
                print("Adjust API 400 — chi tiết lỗi:", resp.text[:1000])

            resp.raise_for_status()
            data = resp.json()
            return pd.DataFrame(data["rows"]), data["totals"]

        raise RuntimeError("Adjust API: vượt quá số lần retry (rate limited)")

    def fetch_filter_values(self, app_token: str, required_filters: str) -> dict:
        """
        Tra danh sách giá trị hợp lệ cho 1 dimension có value-list cố định
        (VD: 'ad_revenue_sources', 'attribution_types'). LƯU Ý: không phải
        mọi filter đều tra được qua endpoint này — 'partner' và 'reattributed'
        KHÔNG hỗ trợ (đã xác nhận qua thực nghiệm, trả lỗi 400
        "is not valid loc=..."), nhưng vẫn dùng được bình thường như filter
        trong fetch_report().
        """
        resp = requests.get(
            ADJUST_FILTERS_URL,
            headers=self.headers,
            params={"app_token__in": app_token, "required_filters": required_filters},
        )
        if not resp.ok:
            print("Adjust filters_data lỗi:", resp.text[:500])
        resp.raise_for_status()
        return resp.json()
