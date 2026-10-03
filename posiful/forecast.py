"""過去の販売食数を学習する、企業別の小規模な回帰予測。"""
from datetime import date
import math
import numpy as np


def _features(day,weather,field):
    return [1.0]+[float(day.weekday()==i) for i in range(1,5)]+[float(day.day<=7),float(weather=='雨' and field)]


def predict_sales(records,companies,target_date,weather):
    target = date.fromisoformat(target_date)
    if weather not in ['晴れ','曇り','雨']:
        raise ValueError('対象日の天気を指定してください。')
    past = [r for r in records if r['served_date'] < target_date]
    if not past or not companies:
        return None
    if target.weekday() >= 5:
        return {'quantity':0,'companies':[],'training_count':len(past),'training_end':max(r['served_date'] for r in past),'reason':'土日は訪問販売なし'}
    details = []
    for company in companies:
        rows = [r for r in past if r['company_id']==company['company_id']]
        if not rows:
            # 一部企業が欠損している場合、全10社の予測として表示しない。
            return None
        field = company.get('work_type')=='現場職'
        if len(rows) >= 8:
            x = np.array([_features(date.fromisoformat(r['served_date']),r['weather'],field) for r in rows])
            y = np.log1p([r['sales_quantity'] for r in rows])
            ridge = np.eye(x.shape[1])*0.05
            ridge[0,0] = 0
            coefficients = np.linalg.solve(x.T@x+ridge,x.T@y)
            predicted = math.expm1(float(np.dot(_features(target,weather,field),coefficients)))
            method = '曜日・第1週・現場職の雨を回帰学習'
        else:
            matching = [r for r in rows if date.fromisoformat(r['served_date']).weekday()==target.weekday()]
            source = matching or rows
            predicted = sum(r['sales_quantity'] for r in source)/len(source)
            method = '履歴が少ないため同曜日平均（なければ全日平均）'
        details.append({'企業':company['company_name'],'予測食数':max(0,round(predicted)),
                        '学習件数':len(rows),'方法':method})
    return {'quantity':sum(r['予測食数'] for r in details),'companies':details,
            'training_count':len(past),'training_end':max(r['served_date'] for r in past),
            'reason':'メニュー別の販売差は未学習。新メニューも企業・日付・天気の需要予測を使用。'}
