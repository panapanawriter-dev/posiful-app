import copy
import unittest
from posiful.history import load_sample
from posiful.forecast import predict_sales


class ForecastTests(unittest.TestCase):
    def setUp(self):
        self.sample = load_sample()

    def predict(self,target,weather='晴れ',records=None):
        return predict_sales(records if records is not None else self.sample['records'],self.sample['companies'],target,weather)

    def test_rain_and_month_start_effects_are_learned(self):
        dry = self.predict('2026-10-08')
        rain = self.predict('2026-10-08','雨')
        dry_by_name = {r['企業']:r['予測食数'] for r in dry['companies']}
        field_names = {c['company_name'] for c in self.sample['companies'] if c['work_type']=='現場職'}
        for row in rain['companies']:
            if row['企業'] in field_names:
                self.assertGreater(row['予測食数'],dry_by_name[row['企業']])
            else:
                self.assertEqual(row['予測食数'],dry_by_name[row['企業']])
        self.assertLess(self.predict('2026-10-06')['quantity'],self.predict('2026-10-13')['quantity'])
        self.assertEqual(dry['quantity'],sum(r['予測食数'] for r in dry['companies']))

    def test_no_future_or_generator_coefficient_leakage(self):
        expected = self.predict('2026-09-15')
        modified = copy.deepcopy(self.sample['records'])
        for row in modified:
            row['normal_quantity'] = 1000000
            row['weather_factor'] = 999
            row['special_factor'] = 999
            if row['served_date'] >= '2026-09-15':
                row['sales_quantity'] = 1000000
        self.assertEqual(self.predict('2026-09-15',records=modified),expected)

    def test_missing_history_and_weekends(self):
        self.assertIsNone(self.predict('2026-09-01'))
        self.assertEqual(self.predict('2026-10-03')['quantity'],0)
        incomplete = [r for r in self.sample['records'] if r['company_id'] != 'C01']
        self.assertIsNone(self.predict('2026-10-08',records=incomplete))

    def test_wednesday_department_closure(self):
        wed = self.predict('2026-10-14')
        tue = self.predict('2026-10-13')
        for idx in [0,1]:
            self.assertLess(wed['companies'][idx]['予測食数'],tue['companies'][idx]['予測食数']*0.4)
