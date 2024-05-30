// Copyright (c) Mysten Labs, Inc.
// SPDX-License-Identifier: Apache-2.0

module deepbook::math {
    /// scaling setting for float
    const FLOAT_SCALING: u64 = 1_000_000_000;
    const FLOAT_SCALING_U128: u128 = 1_000_000_000;

    // <<<<<<<<<<<<<<<<<<<<<<<< Error codes <<<<<<<<<<<<<<<<<<<<<<<<
    const EUnderflow: u64 = 1;
    // <<<<<<<<<<<<<<<<<<<<<<<< Error codes <<<<<<<<<<<<<<<<<<<<<<<<

    // multiply two floating numbers
    public(package) fun unsafe_mul(x: u64, y: u64): u64 {
        let (_, result) = unsafe_mul_round(x, y);
        result
    }

    // multiply two floating numbers
    // also returns whether the result is rounded down
    public(package) fun unsafe_mul_round(x: u64, y: u64): (bool, u64) {
        let x = x as u128;
        let y = y as u128;
        let mut is_round_down = true;
        if ((x * y) % FLOAT_SCALING_U128 == 0) is_round_down = false;
        (is_round_down, (x * y / FLOAT_SCALING_U128) as u64)
    }

    // multiply two floating numbers and assert the result is non zero
    // Note that this function will still round down
    public fun mul(x: u64, y: u64): u64 {
        let (_, result) = unsafe_mul_round(x, y);
        assert!(result > 0, EUnderflow);
        result
    }

    // multiply two floating numbers and assert the result is non zero
    // also returns whether the result is rounded down
    public fun mul_round(x: u64, y: u64): (bool, u64) {
        let (is_round_down, result) = unsafe_mul_round(x, y);
        assert!(result > 0, EUnderflow);
        (is_round_down, result)
    }

    // divide two floating numbers
    public(package) fun unsafe_div(x: u64, y: u64): u64 {
        let (_, result) = unsafe_div_round(x, y);
        result
    }

    // divide two floating numbers
    // also returns whether the result is rounded down
    public(package) fun unsafe_div_round(x: u64, y: u64): (bool, u64) {
        let x = x as u128;
        let y = y as u128;
        let mut is_round_down = true;
        if ((x * (FLOAT_SCALING as u128) % y) == 0) is_round_down = false;
        (is_round_down, (x * (FLOAT_SCALING as u128) / y) as u64)
    }

    // divide two floating numbers and assert the result is non zero
    // also returns whether the result is rounded down
    public fun div_round(x: u64, y: u64): (bool, u64) {
        let (is_round_down, result) = unsafe_div_round(x, y);
        assert!(result > 0, EUnderflow);
        (is_round_down, result)
    }

    public(package) fun count_leading_zeros(mut x: u128): u8 {
        if (x == 0) {
            128
        } else {
            let mut n: u8 = 0;
            if (x & 0xFFFFFFFFFFFFFFFF0000000000000000 == 0) {
                // x's higher 64 is all zero, shift the lower part over
                x = x << 64;
                n = n + 64;
            };
            if (x & 0xFFFFFFFF000000000000000000000000 == 0) {
                // x's higher 32 is all zero, shift the lower part over
                x = x << 32;
                n = n + 32;
            };
            if (x & 0xFFFF0000000000000000000000000000 == 0) {
                // x's higher 16 is all zero, shift the lower part over
                x = x << 16;
                n = n + 16;
            };
            if (x & 0xFF000000000000000000000000000000 == 0) {
                // x's higher 8 is all zero, shift the lower part over
                x = x << 8;
                n = n + 8;
            };
            if (x & 0xF0000000000000000000000000000000 == 0) {
                // x's higher 4 is all zero, shift the lower part over
                x = x << 4;
                n = n + 4;
            };
            if (x & 0xC0000000000000000000000000000000 == 0) {
                // x's higher 2 is all zero, shift the lower part over
                x = x << 2;
                n = n + 2;
            };
            if (x & 0x80000000000000000000000000000000 == 0) {
                n = n + 1;
            };

            n
        }
    }

    #[test_only] use sui::test_utils::assert_eq;

    #[test_only]
    fun pow(mut base: u128, mut exponent: u8): u128 {
        let mut res: u128 = 1;
        while (exponent >= 1) {
            if (exponent % 2 == 0) {
                base = base * base;
                exponent = exponent / 2;
            } else {
                res = res * base;
                exponent = exponent - 1;
            }
        };
        res
    }

    #[test]
    fun test_count_leading_zeros() {
        let mut i: u8 = 0;
        while (i <= 127) {
            assert_eq(count_leading_zeros(pow(2, i) as u128), 128 - i - 1);
            i = i + 1;
        };

        while (i <= 127) {
            assert_eq(count_leading_zeros(pow(2, i) as u128 + 1), 128 - i - 1);
            i = i + 1;
        };
        assert_eq(count_leading_zeros(0), 128);
    }

    #[test]
    fun test_mul() {
        assert_eq(unsafe_mul(1_000_000_000, 1), 1);
        assert_eq(unsafe_mul(9_999_999_999, 1), 9);
        assert_eq(unsafe_mul(9_000_000_000, 1), 9);
    }

    #[test]
    #[expected_failure(abort_code = EUnderflow)]
    fun test_mul_underflow() {
        mul(999_999_999, 1);
    }

    #[test]
    #[expected_failure(abort_code = EUnderflow)]
    fun test_mul_round_check_underflow() {
        mul_round(999_999_999, 1);
    }

    #[test]
    fun test_mul_round() {
        let (mut is_round, mut result) = unsafe_mul_round(1_000_000_000, 1);
        assert_eq(is_round, false);
        assert_eq(result, 1);
        (is_round, result) = unsafe_mul_round(9_999_999_999, 1);
        assert_eq(is_round, true);
        assert_eq(result, 9);
        (is_round, result) = mul_round(9_999_999_999, 1);
        assert_eq(is_round, true);
        assert_eq(result, 9);
    }

    #[test]
    fun test_div() {
        let (mut is_round, mut result) = unsafe_div_round(1, 1_000_000_000);
        assert_eq(is_round, false);
        assert_eq(result, 1);
        (is_round, result) = unsafe_div_round(1, 9_999_999_999);
        assert_eq(is_round, true);
        assert_eq(result, 0);
        (is_round, result) = unsafe_div_round(1, 999_999_999);
        assert_eq(is_round, true);
        assert_eq(result, 1);
    }

    #[test]
    fun test_div_round() {
        let (mut is_round, mut result) = unsafe_div_round(1, 1_000_000_000);
        assert_eq(is_round, false);
        assert_eq(result, 1);
        (is_round, result) = unsafe_div_round(1, 9_999_999_999);
        assert_eq(is_round, true);
        assert_eq(result, 0);
        (is_round, result) = unsafe_div_round(1, 999_999_999);
        assert_eq(is_round, true);
        assert_eq(result, 1);
        (is_round, result) = div_round(1, 999_999_999);
        assert_eq(is_round, true);
        assert_eq(result, 1);
    }

    #[test]
    #[expected_failure(abort_code = EUnderflow)]
    fun test_div_round_check_underflow() {
        div_round(1, 1_000_000_001);
    }
}
