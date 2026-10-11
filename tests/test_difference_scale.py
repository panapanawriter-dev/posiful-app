import unittest

from posiful.core import difference_scales, difference_score, rank
from posiful.search import evaluate_current, rank_targets


class DifferenceScaleTests(unittest.TestCase):
    def menus(self):
        return [dict(menu_id=i, menu_name=str(i), embedding=v,
                     embedding_model='test', ingredients=[dict(name=n, quantity=1, unit='g')])
                for i, v, n in [(1, [1, 0], 'fish'), (2, [1, 1], 'fish'),
                                (3, [0, 1], 'other')]]

    def test_global_maximum_includes_recipes_outside_material_filter(self):
        menus = self.menus()
        scales = difference_scales(menus)
        self.assertAlmostEqual(difference_score(menus[0], [menus[2]], scales), 100)
        result = rank(menus, 'fish', [1])
        self.assertAlmostEqual(result[0]['novelty'], (1 - 2 ** -0.5) * 100)

    def test_current_and_candidates_share_scale_and_total(self):
        menus = self.menus()
        targets = [dict(name='fish', quantity=1, unit='g')]
        candidate = rank_targets(menus, targets, [1], 1)[0]
        current = evaluate_current(menus[1], targets, [menus[0]], 1, menus=menus)
        self.assertAlmostEqual(candidate['novelty'], current['novelty'])
        self.assertAlmostEqual(candidate['priority_score'],
                               (1 + candidate['novelty'] / 100) / 2)

    def test_identical_and_unavailable_comparisons(self):
        menus = self.menus()[:2]
        menus[1]['embedding'] = [1, 0]
        scales = difference_scales(menus)
        self.assertEqual(difference_score(menus[0], [menus[1]], scales), 0)
        self.assertIsNone(difference_score(menus[0], [], scales))
        menus[1]['embedding_model'] = 'different'
        self.assertIsNone(difference_score(menus[0], [menus[1]], scales))
