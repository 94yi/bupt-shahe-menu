import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_site import validate_menu, validate_review  # noqa: E402


class SiteValidationTests(unittest.TestCase):
    def test_live_snapshot_is_valid(self):
        import json

        path = Path(__file__).resolve().parents[1] / "data/menu.json"
        validate_menu(json.loads(path.read_text(encoding="utf-8")))

    def test_review_rejects_personal_or_extra_fields(self):
        review = {
            "schema_version": 1,
            "canteen": "沙河A楼",
            "window_id": 226,
            "window": "测试窗口",
            "goods_id": 14986,
            "dish": "酸辣米粉",
            "meal": "lunch",
            "rating": 4,
            "visit_date": "2026-10-07",
            "comment": "味道不错",
        }
        validate_review(review)
        with self.assertRaises(ValueError):
            validate_review({**review, "student_id": "not-allowed"})
        with self.assertRaises(ValueError):
            validate_review({**review, "canteen": "本部食堂"})
        with self.assertRaises(ValueError):
            validate_review({**review, "rating": 6})


if __name__ == "__main__":
    unittest.main()
