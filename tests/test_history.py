import unittest
from datetime import date
from posiful.history import generate_sample, load_sample, recent_menu_ids, generate_menu_plan, load_menu_plan, surrounding_plans


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.sample = generate_sample()

    def test_size_dates_and_reproducibility(self):
        self.assertEqual(self.sample,load_sample())
        rows = self.sample['records']
        self.assertEqual(len(rows),220)
        self.assertEqual(len({r['company_id'] for r in rows}),10)
        self.assertEqual(len({(r['served_date'],r['company_id']) for r in rows}),220)
        self.assertTrue(all(date.fromisoformat(r['served_date']).weekday() < 5 for r in rows))
        for day in {r['served_date'] for r in rows}:
            total = sum(r['sales_quantity'] for r in rows if r['served_date']==day)
            self.assertTrue(150 <= total <= 250, (day,total))

    def test_wednesday_reduction(self):
        for row in self.sample['records']:
            if row['company_id'] in ['C01','C02']:
                factor = 0.2 if row['weekday']=='水' else 1.0
                self.assertEqual(row['special_factor'],factor)
                self.assertEqual(row['sales_quantity'],max(1,round(row['normal_quantity']*factor*row['weather_factor'])))

    def test_first_week_reduction(self):
        for row in self.sample['records']:
            if row['company_id'] in ['C03','C04','C05','C06']:
                factor = 0.4 if int(row['served_date'][-2:])<=7 else 1.0
                self.assertEqual(row['special_factor'],factor)
            elif row['company_id'] in ['C07','C08','C09','C10']:
                self.assertEqual(row['special_factor'],1.0)

    def test_period_excludes_target_and_future(self):
        rows = [{'served_date':'2026-09-23','menu_id':1,'sales_quantity':10,'company_id':'C01'},
                {'served_date':'2026-09-24','menu_id':2,'sales_quantity':10,'company_id':'C01'},
                {'served_date':'2026-10-01','menu_id':3,'sales_quantity':10,'company_id':'C01'},
                {'served_date':'2026-10-02','menu_id':4,'sales_quantity':10,'company_id':'C02'}]
        self.assertEqual(recent_menu_ids(rows,'2026-10-01',7),[2])
        self.assertEqual(recent_menu_ids(rows,'2026-10-01',7,[]),[])
        self.assertEqual(recent_menu_ids(rows,'2026-10-01',7,['C02']),[])

    def test_menu_links(self):
        from posiful.core import demo_data
        menus = {m['menu_id']:m['menu_name'] for m in demo_data()['menus']}
        self.assertTrue(all(menus[r['menu_id']]==r['menu_name'] for r in self.sample['records']))

    def test_weather_and_combined_effects(self):
        field_ids = {'C02','C06','C08'}
        self.assertEqual({c['company_id'] for c in self.sample['companies'] if c['work_type']=='現場職'},field_ids)
        rows = self.sample['records']
        self.assertEqual({r['weather'] for r in rows},{'晴れ','曇り','雨'})
        for row in rows:
            expected = 1.3 if row['company_id'] in field_ids and row['weather']=='雨' else 1.0
            self.assertEqual(row['weather_factor'],expected)
            self.assertEqual(row['sales_quantity'],max(1,round(row['normal_quantity']*row['special_factor']*expected)))
        for served_date in {r['served_date'] for r in rows}:
            self.assertEqual(len({r['weather'] for r in rows if r['served_date']==served_date}),1)

    def test_planned_comparison_window(self):
        plans = generate_menu_plan()['plans']
        self.assertEqual(generate_menu_plan(),load_menu_plan())
        nearby = surrounding_plans(plans,'2026-10-07')
        self.assertEqual([r['planned_date'] for r in nearby],['2026-10-05','2026-10-06','2026-10-08','2026-10-09'])
        self.assertEqual([r['planned_date'] for r in surrounding_plans(plans,'2026-10-05')],['2026-10-06','2026-10-07'])
        self.assertEqual(len({r['planned_date'] for r in plans}),len(plans))
