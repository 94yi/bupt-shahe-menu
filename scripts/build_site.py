"""Validate public data and build the static review site."""

from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
MEALS = {"breakfast", "lunch", "dinner", "late"}
REVIEW_KEYS = {
    "schema_version", "canteen", "window_id", "window", "goods_id",
    "dish", "meal", "rating", "visit_date", "comment",
}


def bounded_text(value: object, limit: int, *, shahe: bool = False) -> bool:
    return (isinstance(value, str) and value.strip() == value
            and 0 < len(value) <= limit and "\x00" not in value
            and (not shahe or "沙河" in value))


def validate_menu(menu: object) -> None:
    if not isinstance(menu, dict) or menu.get("schema_version") != 1 or menu.get("campus") != "沙河":
        raise ValueError("invalid Shahe menu snapshot")
    if not re.fullmatch(r"\d{8}", str(menu.get("menu_date"))) or not isinstance(menu.get("windows"), list):
        raise ValueError("invalid menu date or windows")
    if len(menu["windows"]) < 5:
        raise ValueError("menu has too few windows")
    dish_count = 0
    for window in menu["windows"]:
        if (not isinstance(window, dict) or type(window.get("id")) is not int
                or not bounded_text(window.get("canteen"), 120, shahe=True)
                or not bounded_text(window.get("window"), 120)
                or not isinstance(window.get("meals"), dict)):
            raise ValueError("invalid menu window")
        for meal, dishes in window["meals"].items():
            if meal not in MEALS or not isinstance(dishes, list):
                raise ValueError("invalid menu meal")
            for dish in dishes:
                if (not isinstance(dish, dict) or not bounded_text(dish.get("name"), 120)
                        or dish.get("id") is not None and type(dish["id"]) is not int):
                    raise ValueError("invalid menu dish")
                dish_count += 1
    if dish_count < 30:
        raise ValueError("menu has too few dishes")


def validate_review(review: object) -> None:
    if not isinstance(review, dict) or set(review) != REVIEW_KEYS or review["schema_version"] != 1:
        raise ValueError("invalid review fields")
    if (not bounded_text(review["canteen"], 120, shahe=True)
            or not bounded_text(review["window"], 120)
            or not bounded_text(review["dish"], 120)
            or not bounded_text(review["comment"], 500)
            or type(review["window_id"]) is not int or not 0 < review["window_id"] < 1_000_000
            or review["goods_id"] is not None and (type(review["goods_id"]) is not int or review["goods_id"] <= 0)
            or review["meal"] not in MEALS
            or type(review["rating"]) is not int or not 1 <= review["rating"] <= 5):
        raise ValueError("invalid review content")
    try:
        visited = date.fromisoformat(review["visit_date"])
    except (TypeError, ValueError):
        raise ValueError("invalid review date") from None
    if not date(2020, 1, 1) <= visited <= datetime.now(ZoneInfo("Asia/Shanghai")).date():
        raise ValueError("review date is outside the allowed range")


def build(output: Path) -> int:
    menu = json.loads((ROOT / "data/menu.json").read_text(encoding="utf-8"))
    validate_menu(menu)
    reviews = []
    for path in sorted((ROOT / "reviews").glob("*.json")):
        try:
            review = json.loads(path.read_text(encoding="utf-8"))
            validate_review(review)
        except (ValueError, KeyError) as error:
            raise ValueError(f"invalid review {path.name}: {error}") from error
        reviews.append(review)
    output.mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "style.css", "app.js"):
        shutil.copy2(ROOT / name, output / name)
    (output / "data").mkdir(exist_ok=True)
    shutil.copy2(ROOT / "data/menu.json", output / "data/menu.json")
    (output / "reviews.json").write_text(
        json.dumps(reviews, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(reviews)


if __name__ == "__main__":
    try:
        count = build(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "_site")
    except (OSError, ValueError, KeyError) as error:
        print(f"Site build failed: {error}", file=sys.stderr)
        raise SystemExit(1) from None
    print(f"Built static site with {count} reviews")
