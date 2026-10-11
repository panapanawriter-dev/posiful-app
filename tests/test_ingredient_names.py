import unittest
from posiful.ingredient_names import canonical_name, normalize_rows
from posiful.recipe import validate_ingredients


class IngredientNameTests(unittest.TestCase):
    def test_alias_and_existing_name(self):
        self.assertEqual(canonical_name(' しょうゆ '), '醤油')
        self.assertEqual(canonical_name('醤油', ['しょうゆ']), 'しょうゆ')
        self.assertEqual(canonical_name('玉 葱'), '玉ねぎ')
        self.assertNotEqual(canonical_name('鶏胸肉'), canonical_name('鶏モモ肉'))
        self.assertNotEqual(canonical_name('生鮭'), canonical_name('塩鮭'))

    def test_merge_convert_and_unknown(self):
        rows, notes = normalize_rows([{'name': '玉葱', 'quantity': 1, 'unit': 'kg'},
                                     {'name': '玉ねぎ', 'quantity': 100, 'unit': 'g'}], merge=True)
        self.assertAlmostEqual(rows[0]['quantity'], 1.1)
        self.assertTrue(notes)
        rows, _ = normalize_rows([{'name': 'しょうゆ', 'quantity': None, 'unit': 'ml'},
                                  {'name': '醤油', 'quantity': 10, 'unit': 'ml'}], merge=True)
        self.assertIsNone(rows[0]['quantity'])

    def test_editor_alias_duplicate_rejected(self):
        rows, _ = normalize_rows([{'name': n, 'quantity': 10, 'unit': 'ml'} for n in ['しょうゆ', '醤油']])
        with self.assertRaises(ValueError):
            validate_ingredients(rows)
