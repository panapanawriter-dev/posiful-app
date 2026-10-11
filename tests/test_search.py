import os
import unittest
from unittest.mock import patch
from copy import deepcopy
from posiful.core import demo_data
from posiful.search import rank_targets

from pathlib import Path

# Streamlitのバージョンにより、相対パスの基準が変わるため、絶対パスで指定する。
APP_PATH = str(Path(__file__).resolve().parents[1] / 'app.py')

class SearchTests(unittest.TestCase):
    def test_quantity_changes_priority_with_unit_conversion(self):
        menus = deepcopy(demo_data()['menus'][:3])
        menus[1]['ingredients'][0]['quantity'] = 60
        targets = [{'name':'鶏もも肉','quantity':6,'unit':'kg'}]
        result = rank_targets(menus, targets, [], 100)
        self.assertEqual(result[0]['menu_id'], 2)
        self.assertEqual(result[0]['target_comparisons'][0]['予測消費量'], 6)
        self.assertEqual(result[0]['quantity_fit'], 1)

    def test_multiple_materials_and_balanced_priority(self):
        menus = deepcopy(demo_data()['menus'][:3])
        menus[1]['ingredients'][1]['quantity'] = 100
        targets = [{'name':'鶏もも肉','quantity':12,'unit':'kg'},
                   {'name':'玉ねぎ','quantity':5,'unit':'kg'}]
        result = rank_targets(menus, targets, [1], 100)
        self.assertEqual(result[0]['menu_id'], 3)
        self.assertEqual(len(result[0]['target_comparisons']), 2)
        self.assertEqual(rank_targets(menus, targets+[{'name':'牛肉','quantity':1,'unit':'kg'}],[],100), [])

    def test_missing_forecast_and_invalid_targets(self):
        menus = demo_data()['menus']
        target = {'name':'鶏もも肉','quantity':5,'unit':'kg'}
        result = rank_targets(menus,[target],[1],None)
        self.assertIsNone(result[0]['quantity_fit'])
        self.assertIsNone(result[0]['target_comparisons'][0]['予測消費量'])
        for targets in [[target,target],[dict(target,quantity=0)],[dict(target,quantity=float('nan'))]]:
            with self.assertRaises(ValueError):
                rank_targets(menus,targets,[],100)

    @patch.dict(os.environ, {'POSIFUL_DEMO_SESSION_ONLY': 'true'})
    def test_multiple_material_inputs_and_detail(self):
        from streamlit.testing.v1 import AppTest
        from datetime import date
        app = AppTest.from_file(APP_PATH).run(timeout=30)
        app.date_input[0].set_value(date(2026,10,13)).run()
        app.multiselect[0].set_value(['鶏もも肉','玉ねぎ']).run()
        self.assertEqual(len(app.exception),0)
        self.assertEqual(len(app.number_input),2)
        next(b for b in app.button if b.label=='消化量を確認').click().run()
        self.assertEqual(len(app.exception),0)
        self.assertTrue(any(m.label=='予想販売数（目安）' for m in app.metric))

    @patch.dict(os.environ, {'POSIFUL_DEMO_SESSION_ONLY': 'true'})
    def test_date_forecast_and_separate_scores(self):
        from datetime import date
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(APP_PATH).run(timeout=30)
        app.date_input[0].set_value(date(2026,10,8)).run()
        self.assertEqual(app.metric[0].value,'198 食')
        self.assertIn('2026-10-08',app.metric[0].label)
        self.assertTrue(any('おススメ度' in m.value for m in app.markdown))
        self.assertFalse(any('相違度' in m.value for m in app.markdown))
        self.assertFalse(any(s.label=='表示順' for s in app.selectbox))
        self.assertEqual(len(app.exception),0)
        next(b for b in app.button if b.key=='admin_レシピ一覧').click().run()
        app.date_input[0].set_value(date(2026,10,8)).run()
        next(s for s in app.selectbox if s.label=='予測日の天気').set_value('雨').run()
        self.assertEqual(app.metric[0].value,'213 食')
