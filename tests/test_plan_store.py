import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from posiful.core import demo_data
from posiful import plan_store

from pathlib import Path

# Streamlitのバージョンにより、相対パスの基準が変わるため、絶対パスで指定する。
APP_PATH = str(Path(__file__).resolve().parents[1] / 'app.py')

class ReplacementTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.patcher = patch.object(plan_store,'STORE_PATH',Path(self.directory.name)/'changes.json')
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_persistent_replacement_and_other_days(self):
        before = plan_store.load_menu_plan()
        original = next(r['menu_name'] for r in before['plans'] if r['planned_date']=='2026-10-07')
        menu = demo_data()['menus'][1]
        plan_store.replace_menu('2026-10-07',menu,original)
        after = plan_store.load_menu_plan()
        row = next(r for r in after['plans'] if r['planned_date']=='2026-10-07')
        self.assertEqual(row['menu_name'],menu['menu_name'])
        self.assertEqual(row['status'],'差し替え済み')
        self.assertEqual([r for r in before['plans'] if r['planned_date']!='2026-10-07'],
                         [r for r in after['plans'] if r['planned_date']!='2026-10-07'])
        with self.assertRaises(ValueError):
            plan_store.replace_menu('2026-10-07',demo_data()['menus'][2],original)
        with self.assertRaises(ValueError):
            plan_store.replace_menu('2026-10-03',menu,'')

    @patch.dict(os.environ, {'POSIFUL_DEMO_SESSION_ONLY': 'true'})
    def test_ui_replacement(self):
        from datetime import date
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(APP_PATH).run(timeout=30)
        app.date_input[0].set_value(date(2026,10,7)).run()
        current_id = next(r['menu_id'] for r in app.session_state.demo_plan['plans'] if r['planned_date']=='2026-10-07')
        next(b for b in app.button if b.label=='消化量を確認' and b.key!=f'detail_{current_id}').click().run()
        self.assertEqual(len(app.exception),0)
        next(b for b in app.button if b.label=='このメニューに差し替える').click().run()
        self.assertEqual(len(app.exception),0)
        self.assertTrue(any('差し替えました' in s.value for s in app.success))
        next(b for b in app.button if b.key=='admin_日替わり予定').click().run()
        self.assertEqual(len(app.exception),0)
        row = next(r for r in app.session_state.demo_plan['plans'] if r['planned_date']=='2026-10-07')
        self.assertEqual(row['status'],'差し替え済み')
