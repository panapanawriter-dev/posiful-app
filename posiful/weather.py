"""福岡市中心部の予報を取得。天気3区分はアプリ独自の簡略分類。"""
import json
from datetime import datetime, date
from zoneinfo import ZoneInfo
from urllib.request import urlopen
from urllib.parse import urlencode
from urllib.error import URLError

JST = ZoneInfo('Asia/Tokyo')


def weather_category(code):
    if code in {0, 1}:
        return '晴れ'
    if code in {2, 3, 45, 48}:
        return '曇り'
    if code in {51,53,55,56,57,61,63,65,66,67,80,81,82,95,96,99}:
        return '雨'
    return None


def fetch_fukuoka():
    query = urlencode({'latitude':33.5902, 'longitude':130.4017,
                       'daily':'weather_code,precipitation_probability_max',
                       'timezone':'Asia/Tokyo', 'forecast_days':16})
    try:
        with urlopen('https://api.open-meteo.com/v1/forecast?'+query, timeout=12) as response:
            raw = json.load(response)
        daily = raw['daily']
        rows = {day: {'code':code, 'weather':weather_category(code), 'rain_probability':probability}
                for day,code,probability in zip(daily['time'],daily['weather_code'],daily['precipitation_probability_max'])}
        return {'days':rows, 'retrieved_at':datetime.now(JST).isoformat(timespec='minutes')}
    except (URLError, TimeoutError, ValueError, KeyError, TypeError):
        raise RuntimeError('福岡の天気予報を取得できません。手動で天気を設定してください。') from None


def forecast_for(payload, target, today=None):
    today = today or datetime.now(JST).date()
    ahead = (date.fromisoformat(target)-today).days
    if not 0 <= ahead <= 15:
        return None
    row = payload['days'].get(target)
    return dict(row, ahead=ahead, reference_only=ahead>7) if row else None
