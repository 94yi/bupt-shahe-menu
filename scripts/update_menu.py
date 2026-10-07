"""Fetch a bounded, public-only Shahe menu snapshot from the BUPT H5 API."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


BASE = "https://hqdc.bupt.edu.cn/mobile/wxapp/"
SOURCE = "https://hqdc.bupt.edu.cn/mb/"
USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"
)
MEALS = {"breakfast": "10", "lunch": "11", "dinner": "12", "late": "13"}
MAX_RESPONSE_BYTES = 4 * 1024 * 1024


def request_menu(endpoint: str, body: dict, token: str) -> dict:
    if endpoint not in {"getWindowList/0", "querygoods"}:
        raise ValueError("only read-only menu endpoints are allowed")
    request = Request(
        BASE + endpoint,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": token,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    with urlopen(request, timeout=25) as response:
        payload = response.read(MAX_RESPONSE_BYTES + 1)
        if len(payload) > MAX_RESPONSE_BYTES:
            raise ValueError("menu response too large")
    result = json.loads(payload)
    if not isinstance(result, dict) or result.get("retcode") != 200:
        raise ValueError("menu query failed or login expired")
    return result


def load_token(token_file: Path | None) -> str:
    token = os.environ.get("BUPT_MENU_TOKEN", "")
    if token_file is not None:
        if token_file.is_symlink() or token_file.stat().st_mode & 0o077:
            raise ValueError("token file must be private (mode 0600)")
        token = json.loads(token_file.read_text(encoding="utf-8"))["token"]
    if not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", token):
        raise ValueError("BUPT_MENU_TOKEN is missing or invalid")
    return token


def _windows_for_meal(date: str, meal_id: str, token: str) -> list[dict]:
    response = request_menu("getWindowList/0", {
        "pageno": 1,
        "predate": date,
        "mealid": meal_id,
        "keyword": "",
        "areaplaceids": [0, 0],
        "sorttype": "",
        "windowid": 0,
    }, token)
    raw = response.get("dataList")
    if not isinstance(raw, list):
        raise ValueError("invalid window list")
    return [item for item in raw[:100] if isinstance(item, dict)]


def _public_dishes(date: str, meal_id: str, window_id: int, token: str) -> list[dict]:
    response = request_menu("querygoods", {
        "predate": date,
        "mealid": meal_id,
        "windowid": window_id,
    }, token)
    raw = response.get("goodslist")
    if not isinstance(raw, list):
        raise ValueError("invalid dish list")
    dishes = []
    seen = set()
    for item in raw[:200]:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        goods_id = item.get("goodsid")
        goods_id = goods_id if type(goods_id) is int and goods_id > 0 else None
        key = (goods_id, name.strip())
        if key in seen:
            continue
        seen.add(key)
        price = item.get("price")
        price = price if type(price) in (int, float) and 0 <= price <= 500 else None
        dishes.append({
            "id": goods_id,
            "name": name.strip()[:120],
            "category": str(item.get("typename") or "")[:80],
            "price_yuan": price,
        })
    return dishes


def build_snapshot(token: str, *, now: datetime | None = None) -> dict:
    instant = now or datetime.now(ZoneInfo("Asia/Shanghai"))
    date = instant.strftime("%Y%m%d")
    windows_by_id: dict[int, dict] = {}
    queries = 0
    failures = 0
    for meal, meal_id in MEALS.items():
        for raw in _windows_for_meal(date, meal_id, token):
            window_id = raw.get("windowid")
            name = raw.get("windowname")
            canteen = raw.get("shopname")
            if type(window_id) is not int or not isinstance(name, str):
                continue
            if "沙河" not in name + str(canteen or ""):
                continue
            entry = windows_by_id.setdefault(window_id, {
                "id": window_id,
                "canteen": str(canteen or "")[:120],
                "window": name[:120],
                "meals": {},
            })
            queries += 1
            try:
                dishes = _public_dishes(date, meal_id, window_id, token)
            except (OSError, ValueError):
                failures += 1
                continue
            if dishes:
                entry["meals"][meal] = dishes
            time.sleep(0.06)
    windows = sorted(
        (entry for entry in windows_by_id.values() if entry["meals"]),
        key=lambda item: (item["canteen"], item["window"]),
    )
    total_dishes = sum(len(items) for window in windows for items in window["meals"].values())
    if len(windows) < 5 or total_dishes < 30:
        raise ValueError(
            f"menu snapshot is incomplete ({len(windows)} windows, "
            f"{total_dishes} dishes, {failures}/{queries} unavailable queries); "
            "keeping the previous version"
        )
    return {
        "schema_version": 1,
        "source": SOURCE,
        "campus": "沙河",
        "captured_at": instant.isoformat(),
        "menu_date": date,
        "windows": windows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/menu.json"))
    args = parser.parse_args()
    try:
        snapshot = build_snapshot(load_token(args.token_file))
        output = args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(output)
    except Exception as error:
        print(f"Menu refresh failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(f"Updated {len(snapshot['windows'])} Shahe windows for {snapshot['menu_date']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
