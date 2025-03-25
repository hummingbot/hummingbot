import unittest

import numpy as np
import pandas as pd

from hummingbot.core.utils import map_df_to_str


class MapDfToStrTest(unittest.TestCase):

    def test_map_df_to_str(self):
        df = pd.DataFrame(data=[0.2, 0, 1, 100., 1.00])
        df = map_df_to_str(df)
        self.assertEqual(df.to_string(), "     0\n"
                                         "0  0.2\n"
                                         "1    0\n"
                                         "2    1\n"
                                         "3  100\n"
                                         "4    1")

    def test_map_df_to_str_applymap_equivalence(self):
        # Test cases with various data types
        data = {
            'col1': [1.2345, 6.7890, np.nan, None, 1],
            'col2': ['abc', 'def', 123, True, False],
            'col3': [pd.Timestamp('2024-07-24'), pd.NaT, pd.Timestamp('2023-01-01'), None, pd.Timestamp('2024-07-25')]
        }
        df = pd.DataFrame(data)

        expected_df = df.applymap(lambda x: np.format_float_positional(x, trim="-") if isinstance(x, float) else x).astype(str)
        actual_df = map_df_to_str(df)

        pd.testing.assert_frame_equal(actual_df, expected_df)
