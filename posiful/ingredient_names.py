"""意味が明確に同じ表記だけ統一。部位・加工状態は消さない。"""
import unicodedata

ALIASES = {
    '醤油': ['醤油', 'しょうゆ', 'しょう油', '正油'],
    '玉ねぎ': ['玉ねぎ', '玉葱', 'たまねぎ', 'タマネギ'],
    'にんじん': ['にんじん', '人参', 'ニンジン'],
    'じゃがいも': ['じゃがいも', 'ジャガイモ', 'じゃが芋'],
    '鶏もも肉': ['鶏もも肉', '鶏モモ肉', '鶏もも', 'とりもも肉'],
    '鶏むね肉': ['鶏むね肉', '鶏胸肉', '鶏ムネ肉', 'とりむね肉'],
    '片栗粉': ['片栗粉', 'かたくり粉'],
    'ごま油': ['ごま油', '胡麻油', 'ゴマ油'],
}


def clean_name(name):
    return ''.join(unicodedata.normalize('NFKC', str(name or '')).split())


def canonical_name(name, known_names=()):
    name = clean_name(name)
    for canonical, aliases in ALIASES.items():
        if name in aliases:
            # 在庫・既存レシピで既に使用されている表記を優先する。
            known = sorted({clean_name(n) for n in known_names if clean_name(n) in aliases})
            return canonical if canonical in known or not known else known[0]
    return name


def normalize_rows(rows, known_names=(), merge=False):
    result, notes = [], []
    for source in rows:
        row = dict(source)
        original = row.get('name')
        row['name'] = canonical_name(original, known_names)
        if row['name'] != original:
            notes.append(f'材料名を統一：{original} → {row["name"]}')
        previous = next((r for r in result if r['name'] == row['name']), None)
        if merge and previous:
            from posiful.core import convert
            if previous.get('quantity') is None or row.get('quantity') is None:
                previous.update(quantity=None)
                notes.append(f'{row["name"]}：複数の記載に不明な量があるため、合計量を確認してください。')
            else:
                try:
                    previous['quantity'] += convert(row['quantity'], row['unit'], previous['unit'])
                    notes.append(f'{row["name"]}：同じ材料の数量を合算しました。原文の重複でないか確認してください。')
                except (ValueError, KeyError):
                    result.append(row)
                    notes.append(f'{row["name"]}：重量と体積などの単位が異なります。確認して1行にまとめてください。')
        else:
            result.append(row)
    return result, list(dict.fromkeys(notes))
