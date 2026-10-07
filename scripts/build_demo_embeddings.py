"""既存サンプルを実APIでベクトル化しローカルだけに保存する。"""
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from posiful.api import embed
from posiful.core import demo_data, cosine
from posiful.demo_embeddings import CACHE_PATH

for line in Path('.env').read_text(encoding='utf-8-sig').splitlines():
    if line.strip() and not line.lstrip().startswith('#') and '=' in line:
        key, value = line.split('=', 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")

cache = {}
for menu in demo_data()['menus']:
    vector, model = embed(menu['feature_text'])
    assert len(vector) == 1536 and cosine(vector, vector) > .999
    cache[menu['menu_name']] = {'feature_text': menu['feature_text'], 'embedding': vector, 'embedding_model': model}
    print(menu['menu_name'], model, len(vector), flush=True)
CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding='utf-8')
print('Saved', len(cache), 'local embeddings')
