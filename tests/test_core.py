import unittest
from posiful.core import demo_data, rank, consumption, cosine


class CoreTests(unittest.TestCase):
    def test_material_filter_and_novelty(self):
        data = demo_data()
        result = rank(data['menus'][:3], '鶏もも肉', [1])
        self.assertEqual([m['menu_id'] for m in result], [3, 2])
        self.assertEqual(rank(data['menus'], '牛肉', [1]), [])

    def test_units_and_expired_stock(self):
        data = demo_data()
        target = data['estimates'][0]['target_date']
        data['estimates'] = [{'menu_id':data['menus'][1]['menu_id'],'target_date':target,'estimated_quantity':30}]
        data['menus'][1]['ingredients'][0]['quantity'] = 120
        data['inventory'] = [{'name':'鶏もも肉','unit':'kg','current_quantity':5,'expiration_date':target},
                             {'name':'玉ねぎ','unit':'kg','current_quantity':3,'expiration_date':target}]
        data['inventory'].append({'name':'鶏もも肉','unit':'kg','current_quantity':100,'expiration_date':'2000-01-01'})
        result = consumption(data['menus'][1], data['inventory'], data['estimates'], target)
        self.assertEqual(result[0]['想定使用量'], 3600)
        self.assertEqual(result[0]['想定残量'], 1400)

    def test_missing_estimate_is_not_zero(self):
        data = demo_data()
        self.assertIsNone(consumption(data['menus'][0], data['inventory'], [], '2026-10-03'))

    def test_different_models_are_not_compared(self):
        data = demo_data()
        data['menus'][1]['embedding_model'] = 'other-model'
        result = rank(data['menus'], '鶏もも肉', [1])
        self.assertIsNone(next(m for m in result if m['menu_id']==2)['novelty'])

    def test_invalid_vectors(self):
        for a,b in [([0,0],[1,0]), ([1],[1,2]), ([float('nan')],[1])]:
            with self.assertRaises(ValueError):
                cosine(a,b)

    def test_streamlit_demo(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file('app.py').run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertGreaterEqual(len([b for b in app.button if b.label == '消化量を確認']), 2)
        next(b for b in app.button if b.label == '消化量を確認').click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 3)
        next(b for b in app.button if b.label == '候補一覧に戻る').click().run()
        self.assertEqual(len(app.multiselect), 1)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 1)
        app.radio[0].set_value('レシピを登録').run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.number_input[0].value, 10)
        app.radio[0].set_value('レシピ一覧').run()
        self.assertEqual(len(app.exception), 0)
        app.radio[0].set_value('日替わり予定').run()
        self.assertEqual(len(app.exception), 0)
        app.radio[0].set_value('提供履歴').run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.metric[0].value, '22 日')
        self.assertEqual(app.metric[1].value, '10 社')


if __name__ == '__main__':
    unittest.main()
