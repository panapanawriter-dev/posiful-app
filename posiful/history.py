"""再現可能な架空の訪問販売・提供履歴。販売数は需要予測ではない。"""
import calendar
import json
import random
from datetime import date, timedelta
from pathlib import Path

SAMPLE_PATH = Path(__file__).resolve().parents[1] / 'data' / 'sample_history_2026_09.json'
PLAN_PATH = SAMPLE_PATH.with_name('sample_menu_plan_2026_10.json')
WEEKDAYS = ['月', '火', '水', '木', '金', '土', '日']


def generate_sample(year=2026, month=9):
    rng = random.Random(202609)
    weather_rng = random.Random(20260901)
    names = ['青葉製作所', 'みなと物流', 'ひかり商事', '東都システム', 'さくら企画',
             '北町サービス', '若葉印刷', '中央設備', 'つばさ食品', '虹ヶ丘研究所']
    companies = []
    for idx, name in enumerate(names, 1):
        companies.append({'company_id':f'C{idx:02}', 'company_name':name+'（架空）',
                          'baseline_quantity':[18,24,14,20,16,22,12,19,15,26][idx-1],
                          'weekday_factors':[0.85,1.0,0.95,1.1,0.8],
                          'wednesday_factor':0.2 if idx <= 2 else 1.0,
                          'work_type':'現場職' if idx in [2,6,8] else '内勤中心',
                          'rain_factor':1.3 if idx in [2,6,8] else 1.0,
                          'first_week_factor':0.4 if 3 <= idx <= 6 else 1.0})
    menu_names = ['鶏の照り焼き弁当','豚の生姜焼き弁当','鶏の唐揚げ弁当','さばの味噌煮弁当',
                  '豚と野菜の炒め弁当','鮭の塩焼き弁当','鶏の甘酢あん弁当','鶏の照り焼き弁当']
    menu_ids = [1,4,5,6,7,8,9,1]
    records = []
    business_day = 0
    for day in range(1, calendar.monthrange(year,month)[1]+1):
        current = date(year,month,day)
        if current.weekday() >= 5:
            continue
        menu_index = business_day % len(menu_names)
        # 同じ訪問エリアを想定し、日ごとの天気を10社で共有する。実測ではない。
        weather = weather_rng.choices(['晴れ','曇り','雨'],weights=[45,25,30])[0]
        daily_inputs = []
        for company in companies:
            weekday_factor = company['weekday_factors'][current.weekday()]
            seasonal_factor = company['wednesday_factor'] if current.weekday()==2 else 1.0
            if day <= 7:
                seasonal_factor *= company['first_week_factor']
            noise = round(rng.uniform(0.92,1.08),4)
            expected_normal = max(1,round(company['baseline_quantity']*weekday_factor*noise))
            weather_factor = company['rain_factor'] if weather=='雨' else 1.0
            daily_inputs.append((company,weekday_factor,seasonal_factor,noise,expected_normal,weather_factor))
        raw_total = sum(max(1,round(normal*special*rain)) for _,_,special,_,normal,rain in daily_inputs)
        # テストの営業規模を10社合計150〜250食に揃え、各社の増減比率は維持する。
        scale = max(155,min(245,raw_total))/raw_total
        for company,weekday_factor,seasonal_factor,noise,normal,weather_factor in daily_inputs:
            expected_normal = max(1,round(normal*scale))
            quantity = max(1,round(expected_normal*seasonal_factor*weather_factor))
            reason = '水曜は一部部門が休み' if current.weekday()==2 and company['wednesday_factor'] < 1 else (
                '第1週は訪問・外出が多い' if day <= 7 and company['first_week_factor'] < 1 else '通常営業')
            if weather_factor > 1:
                reason = ('通常営業' if reason=='通常営業' else reason)+' ／ 雨で現場職の利用増'
            records.append({'served_date':current.isoformat(),'weekday':WEEKDAYS[current.weekday()],
                            'company_id':company['company_id'],'company_name':company['company_name'],
                            'menu_id':menu_ids[menu_index],'menu_name':menu_names[menu_index],
                            'menu_type':'日替わり','normal_quantity':expected_normal,'sales_quantity':quantity,
                            'weekday_factor':weekday_factor,'special_factor':seasonal_factor,
                            'weather':weather,'weather_factor':weather_factor,'work_type':company['work_type'],
                            'daily_noise_factor':noise,'reason':reason,'is_sample':True})
        business_day += 1
    return {'metadata':{'period':f'{year}-{month:02}', 'is_sample':True,'seed':202609,
                        'description':'架空の提供・販売履歴。平日のみ。祝日は通常営業と仮定。第1週は1〜7日。',
                        'wednesday_ratio':0.2,'first_week_ratio':0.4,
                        'rain_ratio':1.3,'weather_seed':20260901,'weather_source':'架空の天気（実測ではない）',
                        'field_company_ids':['C02','C06','C08'],
                        'daily_total_range':[150,250], 'scale_description':'10社合計の営業規模に日別調整。企業ごとの曜日・休み・雨の係数を維持。',
                        'business_days':business_day,'company_count':len(companies),'record_count':len(records)},
            'companies':companies,'records':records}


def load_sample():
    return json.loads(SAMPLE_PATH.read_text(encoding='utf-8'))


def recent_menu_ids(records, target_date, days, company_ids=None):
    """対象日は含めず、直前N暦日の提供を比較対象にする。"""
    end = date.fromisoformat(target_date)
    start = end-timedelta(days=days)
    return sorted({r['menu_id'] for r in records
                   if start <= date.fromisoformat(r['served_date']) < end
                   and r['sales_quantity'] > 0
                   and (company_ids is None or r['company_id'] in company_ids)})


def generate_menu_plan(year=2026, month=10):
    """企業共通の暫定日替わり予定。土日は提供なし。"""
    # 10/5〜10/16は10種類を1種類ずつ配置。相違度による順位付けはしない。
    rotation = [(9,'鶏の甘酢あん弁当'),(10,'鶏と野菜のカレー弁当'),
                (1,'鶏の照り焼き弁当'),(2,'タンドリーチキン弁当'),(3,'蒸し鶏の香味弁当'),
                (4,'豚の生姜焼き弁当'),(5,'鶏の唐揚げ弁当'),(6,'さばの味噌煮弁当'),
                (7,'豚と野菜の炒め弁当'),(8,'鮭の塩焼き弁当')]
    rows = []
    for day in range(1,calendar.monthrange(year,month)[1]+1):
        current = date(year,month,day)
        if current.weekday() >= 5:
            continue
        menu_id,menu_name = rotation[len(rows)%len(rotation)]
        rows.append({'planned_date':current.isoformat(),'weekday':WEEKDAYS[current.weekday()],
                     'menu_id':menu_id,'menu_name':menu_name,'status':'暫定','is_sample':True})
    return {'metadata':{'period':f'{year}-{month:02}','description':'全企業共通の暫定日替わり。土日を除き、祝日は提供ありと仮定。','is_sample':True},'plans':rows}


def load_menu_plan():
    return json.loads(PLAN_PATH.read_text(encoding='utf-8'))


def surrounding_plans(plans,target_date):
    target = date.fromisoformat(target_date)
    return sorted([row for row in plans if target-timedelta(days=1) <= date.fromisoformat(row['planned_date']) <= target+timedelta(days=1)
                   and row['planned_date'] != target_date],key=lambda row:row['planned_date'])
