"""ローカル生成済みのデモEmbeddingを既存セッションにも反映する。"""
import json
from pathlib import Path

CACHE_PATH = Path(__file__).resolve().parents[1] / 'data' / 'local_demo_embeddings.json'


def apply_demo_embeddings(menus):
    if not CACHE_PATH.exists():
        return
    cache = json.loads(CACHE_PATH.read_text(encoding='utf-8'))
    for menu in menus:
        if menu.get('comparison_updated'):
            continue
        cached = cache.get(menu['menu_name'])
        if cached and cached.get('recipe_text') == menu.get('recipe_text'):
            menu.update(cached)
        elif cached and menu.get('embedding_model') == 'demo-manual-v1' and cached['feature_text'] == menu['feature_text']:
            menu.update(embedding=cached['embedding'], embedding_model=cached['embedding_model'])
