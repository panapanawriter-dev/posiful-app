import os
import unittest
from copy import deepcopy
from unittest.mock import patch
from posiful.cloud import sample_payload
from posiful.api import Database

from pathlib import Path

# Streamlitのバージョンにより、相対パスの基準が変わるため、絶対パスで指定する。
APP_PATH = str(Path(__file__).resolve().parents[1] / 'app.py')

class CloudTests(unittest.TestCase):
    def test_payload_vectors_and_counts(self):
        sample = sample_payload()
        self.assertEqual(len(sample['menus']),10)
        self.assertEqual(len(sample['history']),220)
        self.assertEqual(len(sample['inventory']),7)
        self.assertTrue(all(len(m['embedding'])==1536 for m in sample['menus']))
        self.assertTrue(all(m['embedding_model']=='demo-manual-v1' for m in sample['menus']))

    def test_rpc_arguments(self):
        with patch.dict('os.environ',{'SUPABASE_URL':'https://example.supabase.co','SUPABASE_PUBLISHABLE_KEY':'public-test'}),patch('posiful.api.request') as send:
            db = Database('session-test')
            db.replace_menu('2026-10-08',23,2)
            self.assertEqual(send.call_args.args[2],{'target_date':'2026-10-08','new_menu_id':23,'expected_revision':2})
            db.invite('member@example.test')
            self.assertEqual(send.call_args.args[2],{'member_email':'member@example.test'})

    def test_cloud_ui_reads_and_replaces_db_plan(self):
        from streamlit.testing.v1 import AppTest
        from datetime import date
        sample = sample_payload()
        for row in sample['plans']:
            row['revision']=0

        class FakeDatabase:
            def __init__(self,token): pass
            def load(self): return deepcopy(sample)
            def replace_menu(self,target,menu_id,revision):
                row = next(p for p in sample['plans'] if p['planned_date']==target)
                self_previous = row['menu_name']
                if row['revision']!=revision: raise RuntimeError('stale')
                menu = next(m for m in sample['menus'] if m['menu_id']==menu_id)
                row.update(menu_id=menu_id,menu_name=menu['menu_name'],revision=revision+1,status='差し替え済み')
                return {'previous_menu_name':self_previous,'menu_name':row['menu_name']}

        env = {'SUPABASE_URL':'https://example.test','SUPABASE_PUBLISHABLE_KEY':'test','POSIFUL_DEMO_SESSION_ONLY':'false'}
        with patch.dict(os.environ,env),patch('posiful.api.Database',FakeDatabase):
            app = AppTest.from_file(APP_PATH).run(timeout=30)
            self.assertEqual(len(app.exception),0)
            app.date_input[0].set_value(date(2026,10,8)).run()
            self.assertEqual(app.metric[0].value,'198 食')
            current = next(r for r in sample['plans'] if r['planned_date']=='2026-10-08')
            original = current['menu_id']
            next(b for b in app.button if b.label=='消化量を確認' and b.key!=f'detail_{original}').click().run()
            next(b for b in app.button if b.label=='このメニューに差し替える').click().run()
            self.assertEqual(len(app.exception),0)
            self.assertEqual(current['revision'],1)
            self.assertNotEqual(current['menu_id'],original)
            self.assertTrue(any('差し替えました' in s.value for s in app.success))
