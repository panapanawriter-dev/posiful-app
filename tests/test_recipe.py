import json
import unittest
from unittest.mock import patch
from posiful.recipe import structure_recipe, validate_ingredients, comparison_text
from posiful.api import ai_recipe


class RecipeTests(unittest.TestCase):
    def test_comparison_text_has_fixed_order_and_no_quantities(self):
        features = {'genre': '和食', 'cooking_method': '焼く', 'finishing': '甘酢を煮からめる',
                    'flavor': '甘酸っぱい醤油味', 'main_ingredient': '鮭', 'coating': '',
                    'ingredients': [{'name': '鮭', 'quantity': 100, 'unit': 'g'}]}
        text = comparison_text(features)
        self.assertTrue(text.startswith('ジャンル：和食\n主な調理法：焼く'))
        self.assertIn('仕上げ：甘酢を煮からめる', text)
        self.assertIn('衣・食感：不明', text)
        self.assertNotIn('100', text)
    @patch.dict('os.environ', {'POSIFUL_DEMO_SESSION_ONLY': 'true'})
    def test_registration_review_screen(self):
        from streamlit.testing.v1 import AppTest
        raw = {'ingredients': [{'name': '鶏肉', 'quantity': 1200, 'unit': 'g', 'note': ''}],
               'genre': '和食', 'seasoning': '醤油', 'cooking_method': '焼く', 'richness': 'こってり', 'feature_text': '和食'}
        with patch('posiful.api.ai_recipe', return_value=structure_recipe(raw, 10)) as extract:
            app = AppTest.from_file('app.py').run(timeout=30)
            app.radio[0].set_value('レシピを登録').run()
            next(x for x in app.text_input if x.label == 'メニュー名').set_value('テスト料理')
            app.text_area[0].set_value('鶏肉1200gを焼く')
            next(x for x in app.button if x.label == '材料を読み取る').click().run(timeout=30)
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['draft']['ingredients'][0]['quantity'], 120)
            self.assertEqual(extract.call_args.kwargs['servings'], 10)

    def test_total_is_divided_once(self):
        raw = {'ingredients': [{'name': '鶏肉', 'quantity': 1200, 'unit': 'g', 'note': ''}]}
        result = structure_recipe(raw, 10)
        self.assertEqual(result['ingredients'][0]['quantity'], 120)
        self.assertEqual(result['batch_ingredients'][0]['quantity'], 1200)

    def test_unknown_requires_review(self):
        result = structure_recipe({'ingredients': [{'name': '塩', 'quantity': None, 'unit': None}]}, 10)
        self.assertTrue(result['review_notes'])
        with self.assertRaises(ValueError):
            validate_ingredients(result['ingredients'])

    def test_invalid_and_duplicate_rows(self):
        for value in [None, 0, -1, float('nan'), float('inf'), True]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_ingredients([{'name': '肉', 'quantity': value, 'unit': 'g'}])
        with self.assertRaises(ValueError):
            validate_ingredients([{'name': name, 'quantity': 1, 'unit': 'g'} for name in ['肉', ' 肉 ']])

    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test'})
    @patch('posiful.api.request')
    def test_api_extracts_totals(self, request):
        raw = {'ingredients': [{'name': '肉', 'quantity': 1000, 'unit': 'g', 'note': ''}]}
        request.return_value = {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(raw)}}]}
        self.assertEqual(ai_recipe('料理', '肉1kg', 10)['ingredients'][0]['quantity'], 100)
        schema = request.call_args.args[2]['response_format']['json_schema']
        self.assertTrue(schema['strict'])
        request.return_value['choices'][0]['message']['refusal'] = 'refused'
        with self.assertRaises(ValueError):
            ai_recipe('料理', '肉1kg', 10)
