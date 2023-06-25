import unittest
from test.c_profiler_test_case import ProfilerTestCase
from unittest.mock import patch


class TestcProfilerTestCaseMixinBehavior(unittest.TestCase):
    class TestcProfilerTestCaseMixin(ProfilerTestCase):
        def test_basic(self):
            self.assertEqual(1, 1)

    def setUp(self):
        self.test_case = self.TestcProfilerTestCaseMixin()

    @patch('pathlib.Path.mkdir')
    def test_setUpClass_calls_makedirs(self, mock_makedirs):
        self.TestcProfilerTestCaseMixin.setUpClass()
        mock_makedirs.assert_called_once_with(parents=True, exist_ok=True)

    def test_setUp_initializes_profiler_and_current_test(self):
        self.test_case.setUp()
        self.assertIsNotNone(self.test_case.profiler)
        self.assertIsNone(self.test_case.current_test)

    def test_tearDown_fails_without_setUp(self):
        self.test_case.current_test = None
        with self.assertRaises(AttributeError):
            self.test_case.tearDown()

    def test_tearDown_does_not_crash_when_current_test_is_None(self):
        self.test_case.setUp()
        try:
            self.test_case.tearDown()
        except Exception as e:
            self.fail(f"tearDown raised Exception unexpectedly: {e}")

    def test_call_with_profile_fails_without_setup(self):
        @self.test_case.call_with_profile
        def dummy_test():
            self.assertTrue(self.test_case.profiler.is_running())

        with self.assertRaises(AttributeError):
            dummy_test()

    def test_call_with_profile_starts_and_stops_profiler(self):
        self.test_case.setUp()

        @self.test_case.call_with_profile
        def dummy_test():
            test = 2 ** 10000000
            self.test_case.profiler.print_stats()
            return test

        with self.assertRaises(Exception):
            self.test_case.profiler.print_stats()
        self.test_case.profiler.enable()
        self.test_case.profiler.print_stats()
        self.test_case.profiler.disable()
        self.test_case.profiler.clear()
        with self.assertRaises(Exception):
            self.test_case.profiler.print_stats()

        dummy_test()
        self.test_case.profiler.print_stats()

    def test_call_with_profile_sets_current_test(self):
        self.test_case.setUp()

        def dummy_test():
            return 2 ** 10000000

        self.test_case.call_with_profile(dummy_test)()
        self.assertEqual(self.test_case.current_test, 'test_call_with_profile_sets_current_test')

    def test_call_with_profile_sets_current_test_decorated(self):
        self.test_case.setUp()

        @self.test_case.call_with_profile
        def dummy_test():
            return 2 ** 10000000

        dummy_test()
        self.assertEqual(self.test_case.current_test, 'test_call_with_profile_sets_current_test_decorated')


if __name__ == '__main__':
    unittest.main()
