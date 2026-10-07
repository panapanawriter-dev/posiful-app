"""複数材料の希望消費量とメニューの違いを合わせて評価する。"""
import math
from posiful.core import rank, convert, cosine


def evaluate_current(menu, targets, recent, predicted_quantity):
    """維持案は材料未使用も0として評価し、近隣と同じメニューも比較する。"""
    row = dict(menu)
    row['novelty'] = None
    if recent and all(m['embedding_model'] == menu['embedding_model'] for m in recent):
        row['novelty'] = (1-max(cosine(menu['embedding'], m['embedding']) for m in recent))*100
    ingredients = {i['name']: i for i in menu['ingredients']}
    comparisons = []
    for t in targets:
        ingredient = ingredients.get(t['name'])
        used = None if predicted_quantity is None else (0 if ingredient is None else convert(ingredient['quantity'], ingredient['unit'], t['unit'])*predicted_quantity)
        comparisons.append({'材料': t['name'], '単位': t['unit'], '希望消費量': t['quantity'], '予測消費量': used, '差分': None if used is None else used-t['quantity']})
    fit = None if predicted_quantity is None or not comparisons else sum(1/(1+abs(r['差分'])/r['希望消費量']) for r in comparisons)/len(comparisons)
    scores = [s for s in (fit, None if row['novelty'] is None else row['novelty']/200) if s is not None]
    row.update(target_comparisons=comparisons, quantity_fit=fit, priority_score=sum(scores)/len(scores) if scores else None)
    return row


def rank_targets(menus, targets, recent_ids, predicted_quantity):
    if not targets:
        return []
    if len({t['name'] for t in targets}) != len(targets):
        raise ValueError('同じ材料は1行にまとめてください。')
    for t in targets:
        if not math.isfinite(t['quantity']) or t['quantity'] <= 0:
            raise ValueError('希望消費量は正の数を入力してください。')
        convert(t['quantity'], t['unit'], t['unit'])
    candidates = rank(menus, targets[0]['name'], recent_ids)
    result = []
    for menu in candidates:
        ingredients = {i['name']: i for i in menu['ingredients']}
        if not all(t['name'] in ingredients for t in targets):
            continue
        comparisons = []
        for t in targets:
            i = ingredients[t['name']]
            used = None if predicted_quantity is None else convert(i['quantity'], i['unit'], t['unit']) * predicted_quantity
            comparisons.append({'材料': t['name'], '単位': t['unit'], '希望消費量': t['quantity'],
                                '予測消費量': used, '差分': None if used is None else used-t['quantity']})
        fit = None if predicted_quantity is None else sum(1/(1+abs(r['差分'])/r['希望消費量']) for r in comparisons)/len(comparisons)
        novelty = None if menu['novelty'] is None else menu['novelty']/200
        scores = [s for s in (fit, novelty) if s is not None]
        menu.update(target_comparisons=comparisons, quantity_fit=fit,
                    priority_score=sum(scores)/len(scores) if scores else None)
        result.append(menu)
    return sorted(result, key=lambda m: (m['priority_score'] is None, -(m['priority_score'] or 0), m['menu_name']))
