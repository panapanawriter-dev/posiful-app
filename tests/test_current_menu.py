import unittest
from posiful.search import evaluate_current


class CurrentMenuTests(unittest.TestCase):
    def test_current_menu_includes_unused_material_and_repeated_neighbor(self):
        menu = {'menu_name': '料理', 'embedding': [1., 0.], 'embedding_model': 'test',
                'ingredients': [{'name': '肉', 'quantity': 100, 'unit': 'g'}]}
        targets = [{'name': '肉', 'quantity': 20000, 'unit': 'g'},
                   {'name': '玉ねぎ', 'quantity': 1000, 'unit': 'g'}]
        row = evaluate_current(menu, targets, [menu], 200)
        self.assertEqual(row['target_comparisons'][1]['予測消費量'], 0)
        self.assertEqual(row['novelty'], 0)
        self.assertEqual(row['quantity_fit'], .75)
        self.assertEqual(row['priority_score'], .375)

    def test_no_neighbors_keeps_difference_unrated(self):
        menu = {'ingredients': [], 'embedding': [1.], 'embedding_model': 'test'}
        row = evaluate_current(menu, [{'name': '肉', 'quantity': 100, 'unit': 'g'}], [], None)
        self.assertIsNone(row['priority_score'])
