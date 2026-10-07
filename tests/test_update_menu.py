import sys
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'scripts'))
import update_menu

class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 7, 17, tzinfo=timezone(timedelta(hours=8)))
        self.windows = [{'windowid': i, 'windowname': '沙河测试窗口', 'shopname': '沙河食堂'} for i in range(1, 6)]
        self.dishes = [{'id': i, 'name': '测试菜品', 'category': '', 'price_yuan': 10} for i in range(10)]

    def snapshot(self, dishes):
        with patch.object(update_menu, '_windows_for_meal', return_value=self.windows), patch.object(update_menu, '_public_dishes', side_effect=dishes), patch.object(update_menu.time, 'sleep'):
            return update_menu.build_snapshot('unused', now=self.now)

    def test_missing_today_lunch_uses_next_day_and_records_date(self):
        result = self.snapshot(lambda day, meal, window, token: self.dishes if meal == '12' or (meal == '11' and day == '20261008') else [])
        self.assertEqual(result['meal_dates'], {'lunch': '20261008', 'dinner': '20261007'})
        self.assertTrue(all(set(w['meals']) == {'lunch', 'dinner'} for w in result['windows']))

    def test_missing_both_main_meals_does_not_publish(self):
        with self.assertRaisesRegex(ValueError, 'missing both lunch and dinner'):
            self.snapshot(lambda day, meal, window, token: self.dishes if meal == '10' else [])

    def test_partial_query_failure_does_not_publish(self):
        def dishes(day, meal, window, token):
            if window == 3:
                raise OSError('unavailable')
            return self.dishes
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            self.snapshot(dishes)

    def test_unavailable_today_lunch_can_fall_back(self):
        def dishes(day, meal, window, token):
            if meal == '11' and day == '20261007':
                raise ValueError('menu query failed (retcode=500)')
            return self.dishes if meal in ('11', '12') else []
        result = self.snapshot(dishes)
        self.assertEqual(result['meal_dates']['lunch'], '20261008')
