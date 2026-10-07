"""抽出した総量を決定的に1食分へ換算し、保存前に検証する。"""
import math

UNITS = {'g', 'kg', 'ml', 'L', '個'}
COMPARISON_FIELDS = [('genre', 'ジャンル'), ('cooking_method', '主な調理法'),
                     ('finishing', '仕上げ'), ('flavor', '味の特徴'),
                     ('main_ingredient', '主材料'), ('coating', '衣・食感')]


def comparison_text(features):
    return '\n'.join(f'{label}：{str(features.get(key) or "").strip() or "不明"}' for key, label in COMPARISON_FIELDS)


def positive(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def structure_recipe(raw, servings):
    if not positive(servings):
        raise ValueError('食数は正の数で入力してください。')
    result = dict(raw)
    for field in ['genre', 'seasoning', 'cooking_method', 'richness', 'feature_text', 'finishing', 'flavor', 'main_ingredient', 'coating']:
        if str(result.get(field, '')).strip().lower() in {'null', 'none'}:
            result[field] = ''
    ingredients, notes = [], []
    for row in raw.get('ingredients', []):
        name = str(row.get('name') or '').strip()
        quantity, unit = row.get('quantity'), row.get('unit')
        if quantity is not None and not positive(quantity):
            raise ValueError(f'{name}の数量が不正です。')
        if unit is not None and unit not in UNITS:
            raise ValueError(f'{name}の単位が不正です。')
        if quantity is None or unit is None:
            notes.append(f'{name}：数量または単位が不明です。1食分の使用量を入力してください。')
        if row.get('note'):
            notes.append(f'{name}：{row["note"]}')
        if unit in {'ml', 'L'} and any(word in name for word in ['粉', '砂糖', '塩']):
            notes.append(f'{name}：体積で抽出しています。重量で管理する場合はgに変更し、使用量を確認してください。')
        ingredients.append({'name': name, 'quantity': quantity / servings if quantity is not None else None, 'unit': unit})
    if not ingredients:
        raise ValueError('材料を抽出できませんでした。材料名と数量を追記してください。')
    result.update(ingredients=ingredients, batch_ingredients=raw['ingredients'], servings=servings, review_notes=notes)
    if 'main_ingredient' in result:
        result['feature_text'] = comparison_text(result)
    return result


def validate_ingredients(rows):
    cleaned = []
    for row in rows:
        name = str(row.get('name') or '').strip()
        if not name or not positive(row.get('quantity')) or row.get('unit') not in UNITS:
            raise ValueError('全材料に材料名・正の数量・対応する単位を入力してください。')
        cleaned.append({'name': name, 'quantity': float(row['quantity']), 'unit': row['unit']})
    if not cleaned:
        raise ValueError('材料を1件以上入力してください。')
    if len({row['name'] for row in cleaned}) != len(cleaned):
        raise ValueError('同じ材料は1行にまとめてください。')
    return cleaned
