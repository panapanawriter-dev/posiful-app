"""公開デモの予定変更を利用者のセッション内だけで扱う。"""
def replace_in_plan(plan, target, menu, expected_name):
    row = next((r for r in plan['plans'] if r['planned_date']==target),None)
    if row is None:
        raise ValueError('この日には提供予定がありません。')
    if row['menu_name']!=expected_name:
        raise ValueError('予定が変更されています。再検索してください。')
    if menu['menu_type']!='日替わり' or row['menu_name']==menu['menu_name']:
        raise ValueError('別の日替わりメニューを選んでください。')
    previous = row['menu_name']
    row.update(menu_id=menu['menu_id'],menu_name=menu['menu_name'],status='差し替え済み')
    return {'previous_menu_name':previous,'menu_name':menu['menu_name']}
