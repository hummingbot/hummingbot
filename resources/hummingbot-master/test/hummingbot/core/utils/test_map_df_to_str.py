import unittest
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
