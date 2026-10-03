"""暫定予定の差し替えをローカルへ永続保存する。"""
import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from posiful.history import load_menu_plan as load_base_plan

STORE_PATH = Path(__file__).resolve().parents[1] / 'data' / 'menu_plan_changes.json'
_lock = threading.Lock()


def _changes():
    if not STORE_PATH.exists():
        return []
    return json.loads(STORE_PATH.read_text(encoding='utf-8'))


def load_menu_plan():
    plan = load_base_plan()
    by_date = {r['planned_date']:r for r in plan['plans']}
    for change in _changes():
        row = by_date.get(change['planned_date'])
        if row:
            row.update(menu_id=change['menu_id'],menu_name=change['menu_name'],status='差し替え済み')
    return plan


def replace_menu(target_date, menu, expected_name):
    with _lock:
        plan = load_menu_plan()
        row = next((r for r in plan['plans'] if r['planned_date']==target_date),None)
        if row is None:
            raise ValueError('この日には提供予定がありません。提供予定のある日を選択してください。')
        if row['menu_name'] != expected_name:
            raise ValueError('予定が別の操作で変更されています。候補を再検索してください。')
        if menu['menu_type'] != '日替わり':
            raise ValueError('日替わりメニューを選択してください。')
        if row['menu_name'] == menu['menu_name']:
            raise ValueError('すでに同じメニューが予定されています。')
        change = {'planned_date':target_date,'previous_menu_name':row['menu_name'],
                  'menu_id':menu['menu_id'],'menu_name':menu['menu_name'],
                  'changed_at':datetime.now(timezone.utc).isoformat()}
        changes = _changes()+[change]
        STORE_PATH.parent.mkdir(parents=True,exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=STORE_PATH.parent,suffix='.tmp')
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as stream:
                json.dump(changes,stream,ensure_ascii=False,indent=2)
                stream.write('\n')
            os.replace(temporary,STORE_PATH)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return change
