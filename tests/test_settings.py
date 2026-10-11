import unittest
from posiful.settings import configure


class SettingsTests(unittest.TestCase):
    def test_cloud_false_overrides_local_demo(self):
        env = {'POSIFUL_DEMO_SESSION_ONLY': 'true', 'SUPABASE_URL': 'local'}
        self.assertFalse(configure({'POSIFUL_DEMO_SESSION_ONLY': False,
                                    'SUPABASE_URL': 'cloud'}, env))
        self.assertEqual(env['SUPABASE_URL'], 'cloud')

    def test_string_false_is_not_truthy(self):
        self.assertFalse(configure({'POSIFUL_DEMO_SESSION_ONLY': 'false'}, {}))

    def test_local_config_and_default_shared(self):
        self.assertFalse(configure({}, {}))
        env = {'SUPABASE_PUBLISHABLE_KEY': 'local-key'}
        self.assertFalse(configure({}, env))
        self.assertEqual(env['SUPABASE_PUBLISHABLE_KEY'], 'local-key')

    def test_only_expected_keys_are_forwarded(self):
        env = {}
        self.assertTrue(configure({'POSIFUL_DEMO_SESSION_ONLY': True,
                                   'OPENAI_API_KEY': 'test-key', 'OTHER': 'ignored'}, env))
        self.assertEqual(env['OPENAI_API_KEY'], 'test-key')
        self.assertNotIn('OTHER', env)
