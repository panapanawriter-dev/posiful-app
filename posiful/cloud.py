"""ローカルサンプルをDB初期移行用の入力に変換する。"""
from copy import deepcopy
from posiful.core import demo_data
from posiful.plan_store import load_menu_plan


def sample_payload():
    sample = deepcopy(demo_data())
    # DBのvector(1536)に合わせる。仮ベクトルの角度は保ち、AI生成とは明確に区別する。
    for menu in sample['menus']:
        menu['embedding'] += [0.0]*(1536-len(menu['embedding']))
    return {**{k:sample[k] for k in ['menus','inventory','companies','history']},
            'plans':load_menu_plan()['plans']}
