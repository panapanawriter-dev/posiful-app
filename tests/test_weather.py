import unittest
from datetime import date
from posiful.weather import weather_category, forecast_for


class WeatherTests(unittest.TestCase):
    def test_codes_do_not_turn_snow_into_rain(self):
        self.assertEqual(weather_category(0), '晴れ')
        self.assertEqual(weather_category(3), '曇り')
        self.assertEqual(weather_category(61), '雨')
        self.assertIsNone(weather_category(71))

    def test_forecast_horizon(self):
        payload = {'days': {d: {'weather':'雨'} for d in ['2026-10-06','2026-10-14','2026-10-15','2026-10-23']}}
        today = date(2026,10,7)
        self.assertIsNone(forecast_for(payload, '2026-10-06', today))
        self.assertFalse(forecast_for(payload, '2026-10-14', today)['reference_only'])
        self.assertTrue(forecast_for(payload, '2026-10-15', today)['reference_only'])
        self.assertIsNone(forecast_for(payload, '2026-10-23', today))
