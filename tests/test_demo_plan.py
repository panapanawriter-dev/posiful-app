import unittest
from posiful.core import demo_data
from posiful.history import load_menu_plan
from posiful.demo_plan import replace_in_plan


class DemoPlanTests(unittest.TestCase):
    def test_visitors_have_independent_plans(self):
        first,second = load_menu_plan(),load_menu_plan()
        old = next(r for r in first['plans'] if r['planned_date']=='2026-10-08')['menu_name']
        menu = next(m for m in demo_data()['menus'] if m['menu_name']!=old)
        replace_in_plan(first,'2026-10-08',menu,old)
        self.assertEqual(next(r for r in second['plans'] if r['planned_date']=='2026-10-08')['menu_name'],old)
        with self.assertRaises(ValueError):
            replace_in_plan(first,'2026-10-08',menu,old)
