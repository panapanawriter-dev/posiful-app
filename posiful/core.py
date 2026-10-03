"""C案の計算。画面やDB接続に依存しない。"""
import math
from datetime import date, timedelta

UNITS = {"g": ("mass", 1), "kg": ("mass", 1000), "ml": ("volume", 1), "L": ("volume", 1000), "個": ("count", 1)}


def convert(value, source, target):
    if source not in UNITS or target not in UNITS or UNITS[source][0] != UNITS[target][0]:
        raise ValueError(f"単位を換算できません: {source} → {target}")
    return value * UNITS[source][1] / UNITS[target][1]


def cosine(a, b):
    if not a or len(a) != len(b) or not all(math.isfinite(x) for x in a + b):
        raise ValueError("比較できないベクトルです")
    norm = math.sqrt(sum(x*x for x in a) * sum(x*x for x in b))
    if not norm:
        raise ValueError("ゼロベクトルは比較できません")
    return max(-1, min(1, sum(x*y for x, y in zip(a, b)) / norm))


def rank(menus, ingredient, recent_ids):
    recent = [m for m in menus if m["menu_id"] in recent_ids]
    results = []
    for menu in menus:
        if menu["menu_id"] in recent_ids or not any(i["name"] == ingredient for i in menu["ingredients"]):
            continue
        row = dict(menu)
        comparable = all(m["embedding_model"] == menu["embedding_model"] for m in recent)
        if recent and comparable:
            # 最も似た直近日替わりとの距離を使い、似すぎる候補を避ける。
            similarity = max(cosine(menu["embedding"], m["embedding"]) for m in recent)
            row["novelty"] = (1 - similarity) * 100
        else:
            row["novelty"] = None
        results.append(row)
    return sorted(results, key=lambda m: (m["novelty"] is None, -(m["novelty"] or 0), m["menu_name"]))


def consumption(menu, inventory, estimates, target_date):
    estimate = next((e for e in estimates if e["menu_id"] == menu["menu_id"] and e["target_date"] == target_date), None)
    if estimate is None:
        return None
    rows = []
    for ingredient in menu["ingredients"]:
        stocks = [s for s in inventory if s["name"] == ingredient["name"] and s["expiration_date"] >= target_date]
        available = sum(convert(s["current_quantity"], s["unit"], ingredient["unit"]) for s in stocks)
        used = ingredient["quantity"] * estimate["estimated_quantity"]
        rows.append({"材料": ingredient["name"], "単位": ingredient["unit"], "使用可能在庫": available,
                     "想定使用量": used, "想定残量": available-used, "不足量": max(0, used-available)})
    return rows


def demo_data():
    today = date.today().isoformat()
    specs = [("鶏の照り焼き弁当", "和食", "醤油・甘辛", "焼く", "こってり", [1.,0.,0.]),
             ("タンドリーチキン弁当", "インド料理", "スパイス", "焼く", "こってり", [0.2,1.,0.]),
             ("蒸し鶏の香味弁当", "中華", "塩・香味", "蒸す", "さっぱり", [0.1,0.1,1.])]
    menus = []
    for idx, (name, genre, seasoning, method, richness, embedding) in enumerate(specs, 1):
        menus.append({"menu_id": idx, "menu_name": name, "menu_type": "日替わり", "recipe_text": "1食分: 鶏もも肉120g、玉ねぎ50g。",
                      "ingredients": [{"name":"鶏もも肉", "quantity":120, "unit":"g"}, {"name":"玉ねぎ", "quantity":50, "unit":"g"}],
                      "genre":genre, "seasoning":seasoning, "cooking_method":method, "richness":richness,
                      "feature_text":f"{genre}、{seasoning}、{method}、{richness}", "embedding":embedding, "embedding_model":"demo-manual-v1"})
    historical = [
        (4,'豚の生姜焼き弁当','豚肉','和食','生姜・醤油','焼く',[0.9,0.1,0.1]),
        (5,'鶏の唐揚げ弁当','鶏もも肉','和食','醤油・にんにく','揚げる',[0.9,0.2,0.1]),
        (6,'さばの味噌煮弁当','さば','和食','味噌','煮る',[0.8,0.1,0.2]),
        (7,'豚と野菜の炒め弁当','豚肉','中華','塩・香味','炒める',[0.2,0.2,0.9]),
        (8,'鮭の塩焼き弁当','鮭','和食','塩','焼く',[0.7,0.1,0.4]),
        (9,'鶏の甘酢あん弁当','鶏もも肉','中華','甘酢','揚げる',[0.5,0.3,0.6]),
    ]
    for idx,name,main,genre,seasoning,method,embedding in historical:
        menus.append({'menu_id':idx,'menu_name':name,'menu_type':'日替わり',
                      'recipe_text':f'1食分: {main}120g、玉ねぎ50g。{method}。',
                      'ingredients':[{'name':main,'quantity':120,'unit':'g'},{'name':'玉ねぎ','quantity':50,'unit':'g'}],
                      'genre':genre,'seasoning':seasoning,'cooking_method':method,'richness':'こってり',
                      'feature_text':f'{genre}、{seasoning}、{method}',
                      'embedding':embedding,'embedding_model':'demo-manual-v1'})
    from posiful.history import load_sample
    menus.append({'menu_id':10,'menu_name':'鶏と野菜のカレー弁当','menu_type':'日替わり',
                  'recipe_text':'1食分: 鶏もも肉80g、玉ねぎ70g、にんじん40g、じゃがいも60g。食材を炒め、カレー風味で煮込む。',
                  'ingredients':[{'name':'鶏もも肉','quantity':80,'unit':'g'},
                                 {'name':'玉ねぎ','quantity':70,'unit':'g'},
                                 {'name':'にんじん','quantity':40,'unit':'g'},
                                 {'name':'じゃがいも','quantity':60,'unit':'g'}],
                  'genre':'洋食','seasoning':'カレー・スパイス','cooking_method':'煮る','richness':'こってり',
                  'feature_text':'洋食、カレー・スパイス、煮る、鶏もも肉、玉ねぎ、にんじん、じゃがいも',
                  'embedding':[0.2,0.9,0.4],'embedding_model':'demo-manual-v1'})
    # 1食あたりの量。メニューによる消費量の違いを比較できる固定サンプル。
    portions = {1:(115,25),2:(140,35),3:(95,20),4:(110,65),5:(150,15),
                6:(100,30),7:(85,90),8:(105,20),9:(120,60),10:(80,70)}
    for menu in menus:
        main, onion = portions[menu['menu_id']]
        menu['ingredients'][0]['quantity'] = main
        menu['ingredients'][1]['quantity'] = onion
        if menu['menu_id'] == 7:
            menu['ingredients'].append({'name':'にんじん','quantity':35,'unit':'g'})
        ingredients_text = '、'.join(f"{i['name']}{i['quantity']}{i['unit']}" for i in menu['ingredients'])
        menu['recipe_text'] = f"1食分: {ingredients_text}。{menu['seasoning']}の味付けで{menu['cooking_method']}。"
    sample = load_sample()
    from posiful.forecast import predict_sales
    prediction = predict_sales(sample['records'],sample['companies'],today,'晴れ')
    expiry = (date.today()+timedelta(days=21)).isoformat()
    # テスト用の固定在庫。販売予測や献立から必要量を逆算しない。
    inventory = [{'name':name,'current_quantity':quantity,'unit':'kg','expiration_date':expiry}
                 for name,quantity in [('鶏もも肉',90),('玉ねぎ',55),('豚肉',30),
                                       ('さば',15),('鮭',15),('にんじん',5),('じゃがいも',7)]]
    return {"menus":menus, "inventory":inventory, 'stock_revision':3,
            "estimates":[] if prediction is None else [{"menu_id":m["menu_id"], "target_date":today, "estimated_quantity":prediction['quantity']} for m in menus],
            'companies':sample['companies'],'history':sample['records']}
