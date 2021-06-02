import unittest
from hummingbot.strategy.__utils__.ring_buffer import RingBuffer
import numpy as np
from decimal import Decimal


class RingBufferTest(unittest.TestCase):
    BUFFER_LENGTH = 30

    def setUp(self) -> None:
        self.buffer = RingBuffer(self.BUFFER_LENGTH)

    def fill_buffer_with_zeros(self):
        for i in range(self.BUFFER_LENGTH):
            self.buffer.add_value(0)

    def test_add_value(self):
        self.buffer.add_value(1)
        self.assertEqual(self.buffer.get_as_numpy_array().size, 1)

    def test_is_full(self):
        self.assertFalse(self.buffer.is_full)  # Current occupation = 0
        self.buffer.add_value(1)
        self.assertFalse(self.buffer.is_full)  # Current occupation = 1
        for i in range(self.BUFFER_LENGTH - 2):
            self.buffer.add_value(i)
        self.assertFalse(self.buffer.is_full)  # Current occupation = BUFFER_LENGTH-1
        self.buffer.add_value(1)
        self.assertTrue(self.buffer.is_full)  # Current occupation = BUFFER_LENGTH

    def test_add_when_full(self):
        for i in range(self.BUFFER_LENGTH):
            self.buffer.add_value(1)
        self.assertTrue(self.buffer.is_full)
        # Filled with ones, total sum equals BUFFER_LENGTH
        self.assertEqual(np.sum(self.buffer.get_as_numpy_array()), self.BUFFER_LENGTH)
        # Add zeros till length/2 check total sum has decreased accordingly
        mid_point = self.BUFFER_LENGTH // 2
        for i in range(mid_point):
            self.buffer.add_value(0)
        self.assertEqual(np.sum(self.buffer.get_as_numpy_array()), self.BUFFER_LENGTH - mid_point)
        # Add remaining zeros to complete length, sum should go to zero
        for i in range(self.BUFFER_LENGTH - mid_point):
            self.buffer.add_value(0)
        self.assertEqual(np.sum(self.buffer.get_as_numpy_array()), 0)

    def test_mean(self):
        # When not full, mean=nan
        self.assertTrue(np.isnan(self.buffer.mean_value))
        for i in range(self.BUFFER_LENGTH // 2):
            self.buffer.add_value(1)
        # Still not full, mean=nan
        self.assertTrue(np.isnan(self.buffer.mean_value))
        for i in range(self.BUFFER_LENGTH - self.BUFFER_LENGTH // 2):
            self.buffer.add_value(1)
        # Once full, mean != nan
        self.assertEqual(self.buffer.mean_value, 1.0)

    def test_mean_with_alternated_samples(self):
        for i in range(self.BUFFER_LENGTH * 3):
            self.buffer.add_value(2 * ((-1) ** i))
            if self.buffer.is_full:
                self.assertEqual(self.buffer.mean_value, 0)

    def test_std_dev_and_variance(self):
        # When not full, stddev=var=nan
        self.assertTrue(np.isnan(self.buffer.std_dev))
        self.assertTrue(np.isnan(self.buffer.variance))
        for i in range(self.BUFFER_LENGTH // 2):
            self.buffer.add_value(1)
        # Still not full, stddev=var=nan
        self.assertTrue(np.isnan(self.buffer.std_dev))
        self.assertTrue(np.isnan(self.buffer.variance))
        for i in range(self.BUFFER_LENGTH - self.BUFFER_LENGTH // 2):
            self.buffer.add_value(1)
        # Once full, std_dev = variance = 0 in this case
        self.assertEqual(self.buffer.std_dev, 0)
        self.assertEqual(self.buffer.variance, 0)

    def test_std_dev_and_variance_with_alternated_samples(self):
        for i in range(self.BUFFER_LENGTH * 3):
            self.buffer.add_value(2 * ((-1)**i))
            if self.buffer.is_full:
                self.assertEqual(self.buffer.std_dev, 2)
                self.assertEqual(self.buffer.variance, 4)

    def test_get_last_value(self):
        self.assertTrue(np.isnan(self.buffer.get_last_value()))
        expected_values = [-2, -1.0, 0, 3, 1e10]
        for value in expected_values:
            self.buffer.add_value(value)
            self.assertEqual(self.buffer.get_last_value(), value)

        # Decimals are casted when added to numpy array as np.float64. No exact match
        value = Decimal(3.141592653)
        self.buffer.add_value(value)
        self.assertAlmostEqual(float(value), self.buffer.get_last_value(), 6)
