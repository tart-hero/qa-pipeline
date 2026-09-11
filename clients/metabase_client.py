"""
Client gọi Metabase REST API.

Ghi chú quan trọng rút ra từ quá trình debug thực tế (xem docs/reconciliation.md):
- Question "Cohort ROAS + Revenue by Campain" (card_id=81) là 1 Native SQL
  Question ĐỘC LẬP, không nằm trong Dashboard nào cả — dù UI hiển thị các ô
  filter y hệt dashboard filter. Vì vậy ta dùng endpoint
  `/api/card/{id}/query`, KHÔNG dùng `/api/dashboard/.../dashcard/.../query`.
- `card["parameters"]` đã chứa sẵn đúng `id`/`type`/`target` cho từng filter
  (lấy từ `template-tags` trong SQL gốc) — không tự dựng lại tay, luôn lấy
  nguyên từ response API để tránh sai `target`.
"""
from typing import Optional

import pandas as pd
import requests


class MetabaseClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {"x-api-key": api_key}
        self._card_cache: dict[int, dict] = {}

    def get_card(self, card_id: int) -> dict:
        """Lấy metadata đầy đủ của 1 Card/Question, cache lại trong session."""
        if card_id not in self._card_cache:
            resp = requests.get(f"{self.base_url}/api/card/{card_id}", headers=self.headers)
            resp.raise_for_status()
            self._card_cache[card_id] = resp.json()
        return self._card_cache[card_id]

    def build_parameters(self, card_id: int, **overrides) -> list[dict]:
        """
        Build payload `parameters` cho query, dựa trên `card["parameters"]`
        thật (không tự đoán target). Chỉ filter nào được truyền giá trị
        (khác None) mới được đưa vào — filter nào không truyền coi như để
        trống trên UI, khớp cú pháp `[[AND {{...}}]]` trong SQL.

        Ví dụ:
            mb.build_parameters(81, cohort_date="2026-07-17~2026-08-12",
                                 game=["Game A"], active_only=[True])
        """
        card = self.get_card(card_id)
        result = []
        for p in card["parameters"]:
            slug = p["slug"]
            if overrides.get(slug) is None:
                continue
            result.append({
                "id": p["id"],
                "type": p["type"],
                "target": p["target"],
                "value": overrides[slug],
            })
        return result

    def query_card(self, card_id: int, parameters: Optional[list[dict]] = None) -> pd.DataFrame:
        """Chạy Question, trả về DataFrame. `rows` từ Metabase là list-of-list
        (không có tên cột đi kèm) — phải tự map từ `data.cols[i].name`."""
        url = f"{self.base_url}/api/card/{card_id}/query"
        resp = requests.post(url, headers=self.headers, json={"parameters": parameters or []})
        resp.raise_for_status()
        result = resp.json()
        cols = [c["name"] for c in result["data"]["cols"]]
        return pd.DataFrame(result["data"]["rows"], columns=cols)
