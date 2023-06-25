import cProfile
import inspect
import os
import unittest
from pathlib import Path
from pstats import Stats


class ProfilerTestCase(unittest.TestCase):
    data_dir: Path = Path(os.path.dirname(__file__)) / "profiling-data"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.data_dir.mkdir(parents=True, exist_ok=True)

    def setUp(self):
        super().setUp()

        # Profiler
        self.profiler = cProfile.Profile()
        self.current_test = None

    def tearDown(self):
        """finish any test"""
        try:
            p = Stats(self.profiler)
            p.strip_dirs()
            p.sort_stats('cumtime')
            p.print_stats()
            p.dump_stats(f"{self.data_dir}/{self.current_test}.pstats")
            print("\n--->>>")
        except AttributeError:
            raise AttributeError("tearDown() called without setUp()")
        except TypeError:
            pass
        finally:
            pass
        super().tearDown()

    # Test decorator
    def call_with_profile(self, func):
        """Decorator to enable profiling for the decorated function."""

        def call_f(*args, **kwargs):
            self.current_test = inspect.currentframe().f_back.f_code.co_name
            print(f"Profiling {func.__name__} in {self.current_test}")
            try:
                with self.profiler:
                    return func(*args, **kwargs)
            except AttributeError:
                raise AttributeError("tearDown() called without setUp()")

        return call_f
