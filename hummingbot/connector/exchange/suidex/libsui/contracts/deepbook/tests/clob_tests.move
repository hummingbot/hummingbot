// Copyright (c) Mysten Labs, Inc.
// SPDX-License-Identifier: Apache-2.0

#[test_only]
/// Tests for the pool module.
/// They are sequential and based on top of each other.
module deepbook::clob_test {
    use sui::clock::{Self, Clock};
    use sui::coin::{Self, mint_for_testing, burn_for_testing};
    use sui::sui::SUI;
    use sui::test_scenario::{Self as test, Scenario, next_tx, ctx, end, TransactionEffects};
    use sui::test_utils::assert_eq;
    use deepbook::clob_v2::{Self as clob, Pool, PoolOwnerCap, WrappedPool, Order, USD, account_balance, get_pool_stat,
        order_id_for_test, list_open_orders, mint_account_cap_transfer, borrow_mut_pool};
    use deepbook::custodian_v2::{Self as custodian, AccountCap, account_owner};

    const MIN_PRICE: u64 = 0;
    const MAX_PRICE: u64 = (1u128 << 64 - 1) as u64;
    const MIN_ASK_ORDER_ID: u64 = 1 << 63;
    const FLOAT_SCALING: u64 = 1000000000;
    const TIMESTAMP_INF: u64 = (1u128 << 64 - 1) as u64;
    const FILL_OR_KILL: u8 = 2;
    const POST_OR_ABORT: u8 = 3;
    const CLIENT_ID_ALICE: u64 = 0;
    const CLIENT_ID_BOB: u64 = 1;
    const CANCEL_OLDEST: u8 = 0;

    #[test] fun test_full_transaction() { let _ = test_full_transaction_(scenario()); }

    #[test] fun test_place_market_buy_order_with_skipping_self_matching() { let _ = test_place_market_buy_order_with_skipping_self_matching_(scenario()); }

    #[test] fun test_place_market_sell_order_with_skipping_self_matching() { let _ = test_place_market_sell_order_with_skipping_self_matching_(scenario()); }

    #[test] fun test_place_limit_order_fill_or_kill() { let _ = test_place_limit_order_fill_or_kill_(scenario()); }

    #[test] fun test_place_limit_order_post_or_abort() { let _ = test_place_limit_order_post_or_abort_(scenario()); }

    #[test] fun test_place_limit_order_with_skipping_self_matching() { let _ = test_place_limit_order_with_skipping_self_matching_(scenario()); }

    #[test] fun test_absorb_all_liquidity_bid_side_with_customized_tick(
    ) { let _ = test_absorb_all_liquidity_bid_side_with_customized_tick_(scenario()); }

    #[test] fun test_absorb_all_liquidity_ask_side_with_customized_tick(
    ) { let _ = test_absorb_all_liquidity_ask_side_with_customized_tick_(scenario()); }

    #[test] fun test_swap_exact_quote_for_base(
    ) { let _ = test_swap_exact_quote_for_base_(scenario()); }

    #[test] fun test_pool_with_small_fee_example() { let _ = test_pool_with_small_fee_example_(scenario()); }

    #[test] fun test_swap_exact_quote_for_base_with_skipping_self_matching(
    ) { let _ = test_swap_exact_quote_for_base_with_skipping_self_matching_(scenario()); }

    #[test] fun test_swap_exact_base_for_quote(
    ) { let _ = test_swap_exact_base_for_quote_(scenario()); }

    #[test] fun test_deposit_withdraw() { let _ = test_deposit_withdraw_(scenario()); }

    #[test] fun test_inject_and_match_taker_bid_with_quote_quantity(
    ) { let _ = test_inject_and_match_taker_bid_with_quote_quantity_(scenario()); }

    #[test] fun test_inject_and_match_taker_bid_with_quote_quantity_zero_lot(
    ) { let _ = test_inject_and_match_taker_bid_with_quote_quantity_zero_lot_(scenario()); }

    #[test] fun test_inject_and_match_taker_bid_with_quote_quantity_partial_lot(
    ) { let _ = test_inject_and_match_taker_bid_with_quote_quantity_partial_lot_(scenario()); }

    #[test] fun test_swap_exact_base_for_quote_min_size(
    ) { let _ = test_swap_exact_base_for_quote_min_size_(scenario()); }

    #[test, expected_failure(abort_code = clob::EInvalidQuantity)] fun test_place_order_less_than_min_size_error(
    ) { let _ = test_place_order_less_than_min_size_error_(scenario()); }

    #[test] fun test_inject_and_match_taker_bid() { let _ = test_inject_and_match_taker_bid_(scenario()); }

    #[test] fun test_inject_and_match_taker_bid_with_skip_self_matching() { let _ = test_inject_and_match_taker_bid_with_skipping_self_matching_(scenario()); }

    #[test] fun test_inject_and_match_taker_bid_with_maker_order_not_fully_filled(
    ) { let _ = test_inject_and_match_taker_bid_with_maker_order_not_fully_filled_(scenario()); }

    #[test] fun test_inject_and_match_taker_ask() { let _ = test_inject_and_match_taker_ask_(scenario()); }

    #[test] fun test_inject_and_match_taker_ask_with_skipping_self_matching() { let _ = test_inject_and_match_taker_ask_with_skipping_self_matching_(scenario()); }

    #[test] fun test_inject_and_match_taker_bid_with_expiration(
    ) { let _ = test_inject_and_match_taker_bid_with_expiration_(scenario()); }

    #[test] fun test_inject_and_match_taker_bid_with_quote_quantity_and_expiration(
    ) { let _ = test_inject_and_match_taker_bid_with_quote_quantity_and_expiration_(scenario()); }

    #[test] fun test_inject_and_match_taker_ask_with_expiration() {
        let _ = test_inject_and_match_taker_ask_with_expiration_(scenario());
    }

    #[test] fun test_withdraw_fees() {
        let _ = test_withdraw_fees_(scenario());
    }

    #[test, expected_failure(abort_code = clob::EIncorrectPoolOwner)] fun test_withdraw_fees_with_incorrect_pool_owner() {
        let _ = test_withdraw_fees_with_incorrect_pool_owner_(scenario());
    }

    #[test] fun test_inject_and_price_limit_affected_match_taker_bid() {
        let _ = test_inject_and_price_limit_affected_match_taker_bid_(
            scenario()
        );
    }

    #[test] fun test_inject_and_price_limit_affected_match_taker_ask() {
        let _ = test_inject_and_price_limit_affected_match_taker_ask_(
            scenario()
        );
    }

    #[test] fun test_remove_order() { let _ = test_remove_order_(scenario()); }

    #[test] fun test_remove_all_orders() { let _ = test_remove_all_orders_(scenario()); }

    #[test] fun test_cancel_and_remove() { let _ = test_cancel_and_remove_(scenario()); }

    #[test] fun test_batch_cancel() { let _ = test_batch_cancel_(scenario()); }

    #[test] fun test_clean_up_expired_orders() { let _ = test_clean_up_expired_orders_(scenario()); }

    #[test] fun test_partial_fill_and_cancel() { let _ = test_partial_fill_and_cancel_(scenario()); }

    #[test] fun test_list_open_orders() {
        let _ = test_list_open_orders_(
            scenario()
        );
    }

    #[test] fun test_list_open_orders_empty() {
        let _ = test_list_open_orders_empty_(
            scenario()
        );
    }

    #[test] fun get_best_price() {
        let _ = get_market_price_(
            scenario()
        );
    }

    #[test] fun get_level2_book_status_bid_side() {
        let _ = get_level2_book_status_bid_side_(
            scenario()
        );
    }

    #[test] fun get_level2_book_status_ask_side() {
        let _ = get_level2_book_status_ask_side_(
            scenario()
        );
    }

    #[test]
    fun test_inject_and_price_limit_affected_match_taker_ask_returned_pool() {
        test_inject_and_price_limit_affected_match_taker_ask_returned_pool_(
            scenario()
        );
    }

    #[test]
    fun test_swap_exact_quote_for_base_with_metadata() {
        test_swap_exact_quote_for_base_with_metadata_(
            scenario()
        );
    }

    #[test]
    fun test_swap_exact_base_for_quote_with_metadata() {
        test_swap_exact_base_for_quote_with_metadata_(
            scenario()
        );
    }

    #[test]
    fun test_place_market_order_with_metadata() {
        test_place_market_order_with_metadata_(
            scenario()
        );
    }

    #[test]
    fun test_place_limit_order_with_metadata() {
        test_place_limit_order_with_metadata_(
            scenario()
        );
    }

    fun get_market_price_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        let owner = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(5000000, 2500000, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);{
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let (bid_price, ask_price) = clob::get_market_price<SUI, USD>(&pool);
            assert_eq(option::is_none(&bid_price), true);
            assert_eq(option::is_none(&ask_price), true);
            test::return_shared(pool);
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 100000;
            let alice_deposit_USDC: u64 = 100000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 4 * FLOAT_SCALING, 500, 500, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 4 * FLOAT_SCALING, 500, 500, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 3 * FLOAT_SCALING, 1000, 1000, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 1000, 1000, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 1000, 1000, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 100000;
            let alice_deposit_USDC: u64 = 100000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 15 * FLOAT_SCALING, 500, 500, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 15 * FLOAT_SCALING, 500, 500, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 14 * FLOAT_SCALING, 500, 500, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 14 * FLOAT_SCALING, 500, 500, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 13 * FLOAT_SCALING, 1000, 1000, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 12 * FLOAT_SCALING, 1000, 1000, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 12 * FLOAT_SCALING, 1000, 1000, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        next_tx(&mut test, alice);{
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let (bid_price, ask_price) = clob::get_market_price<SUI, USD>(&pool);
            assert_eq(*option::borrow(&bid_price), 5 * FLOAT_SCALING);
            assert_eq(*option::borrow(&ask_price), 12 * FLOAT_SCALING);
            test::return_shared(pool);
        };

        end(test)
    }

    fun get_level2_book_status_bid_side_(mut test: Scenario): TransactionEffects {
        let (alice, _) = people();
        let owner = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(5000000, 2500000, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let clock = test::take_shared<Clock>(&test);
            let (prices, depth) = clob::get_level2_book_status_bid_side(
                &pool,
                1 * FLOAT_SCALING,
                15 * FLOAT_SCALING,
                &clock
            );
            let prices_cmp = vector::empty<u64>();
            let depth_cmp = vector::empty<u64>();
            assert!(prices == prices_cmp, 0);
            assert!(depth == depth_cmp, 0);
            test::return_shared(clock);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 100000;
            let alice_deposit_USDC: u64 = 100000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 4 * FLOAT_SCALING, 500, 500, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 4 * FLOAT_SCALING, 500, 500, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order_with_expiration(&mut pool, CLIENT_ID_ALICE, 3_500_000_000, 1000, 1000, true,
                CANCEL_OLDEST, 0, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 3 * FLOAT_SCALING, 1000, 1000, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 1000, 1000, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order_with_expiration(&mut pool, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 1000, 1000, true,
                CANCEL_OLDEST, 0, &account_cap, ctx(&mut test));
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        // test get_level2_book_status_bid_side
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let clock = test::take_shared<Clock>(&test);
            let order = clob::get_order_status(&pool, order_id_for_test(0, true), &account_cap);
            let order_cmp = clob::test_construct_order(0, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, true, account_cap_user);
            assert!(order == &order_cmp, 0);
            let (prices, depth) = clob::get_level2_book_status_bid_side(
                &pool,
                1 * FLOAT_SCALING,
                15 * FLOAT_SCALING,
                &clock
            );
            let prices_cmp = vector<u64>[2 * FLOAT_SCALING, 3 * FLOAT_SCALING, 4 * FLOAT_SCALING, 5 * FLOAT_SCALING];
            let depth_cmp = vector<u64>[1000, 1000, 1000, 1000];
            assert!(prices == prices_cmp, 0);
            assert!(depth == depth_cmp, 0);
            test::return_shared(clock);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        end(test)
    }

    fun get_level2_book_status_ask_side_(mut test: Scenario): TransactionEffects {
        let (alice, _) = people();
        let owner = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(5000000, 2500000, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let clock = test::take_shared<Clock>(&test);
            let (prices, depth) = clob::get_level2_book_status_ask_side(
                &pool,
                1 * FLOAT_SCALING,
                10 * FLOAT_SCALING,
                &clock
            );
            let prices_cmp = vector::empty<u64>();
            let depth_cmp = vector::empty<u64>();
            assert!(prices == prices_cmp, 0);
            assert!(depth == depth_cmp, 0);
            test::return_shared(clock);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 100000;
            let alice_deposit_USDC: u64 = 100000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 4 * FLOAT_SCALING, 500, 500, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 4 * FLOAT_SCALING, 500, 500, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order_with_expiration(&mut pool, CLIENT_ID_ALICE, 3_500_000_000, 1000, 1000, false,
                CANCEL_OLDEST, 0, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 3 * FLOAT_SCALING, 1000, 1000, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 1000, 1000, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order_with_expiration(&mut pool, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 1000, 1000, false,
                CANCEL_OLDEST, 0, &account_cap, ctx(&mut test));
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        // test get_level2_book_status_ask_side
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let clock = test::take_shared<Clock>(&test);
            let order = clob::get_order_status(&pool, order_id_for_test(0, false), &account_cap);
            let order_cmp = clob::test_construct_order(0, CLIENT_ID_ALICE,  5 * FLOAT_SCALING, 500, 500, false, account_cap_user);
            assert!(order == &order_cmp, 0);
            let (prices, depth) = clob::get_level2_book_status_ask_side(
                &pool,
                1 * FLOAT_SCALING,
                10 * FLOAT_SCALING,
                &clock
            );
            let prices_cmp = vector<u64>[2 * FLOAT_SCALING, 3 * FLOAT_SCALING, 4 * FLOAT_SCALING, 5 * FLOAT_SCALING];
            let depth_cmp = vector<u64>[1000, 1000, 1000, 1000];
            assert!(prices == prices_cmp, 0);
            assert!(depth == depth_cmp, 0);
            test::return_shared(clock);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        end(test)
    }

    fun test_list_open_orders_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        let owner = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(5000000, 2500000, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 10000;
            let alice_deposit_USDC: u64 = 10000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 1000, 1000, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 1 * FLOAT_SCALING, 10000, 10000, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        // test list_open_orders
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let open_orders = list_open_orders(&pool, &account_cap);
            let mut open_orders_cmp = vector::empty<Order>();
            vector::push_back(
                &mut open_orders_cmp,
                clob::test_construct_order(0, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, false, account_cap_user)
            );
            vector::push_back(
                &mut open_orders_cmp,
                clob::test_construct_order(1, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, false, account_cap_user)
            );
            vector::push_back(
                &mut open_orders_cmp,
                clob::test_construct_order(2, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 1000, 1000, false, account_cap_user)
            );
            vector::push_back(
                &mut open_orders_cmp,
                clob::test_construct_order(0, CLIENT_ID_ALICE, 1 * FLOAT_SCALING, 10000, 10000, true, account_cap_user)
            );
            assert!(open_orders == open_orders_cmp, 0);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        // test match (bid side)
        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let (base_quantity_filled, quote_quantity_filled) = clob::test_match_bid(
                &mut pool,
                &account_cap,
                CLIENT_ID_BOB,
                1500,
                MAX_PRICE,
                0,
            );
            assert!(base_quantity_filled == 1500, 0);
            assert!(quote_quantity_filled == 4500 + 10 + 13, 0);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            let alice_account_cap = test::take_from_address<AccountCap>(&test, alice);
            clob::check_balance_invariants_for_account(&alice_account_cap, quote_custodian, base_custodian, &pool);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(bob, account_cap);
            test::return_to_address<AccountCap>(alice, alice_account_cap);
        };

        // test list_open_orders after match
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let open_orders = list_open_orders(&pool, &account_cap);
            let mut open_orders_cmp = vector::empty<Order>();
            vector::push_back(
                &mut open_orders_cmp,
                clob::test_construct_order(1, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, false, account_cap_user)
            );
            vector::push_back(
                &mut open_orders_cmp,
                clob::test_construct_order(0, CLIENT_ID_ALICE, 1 * FLOAT_SCALING, 10000, 10000, true, account_cap_user)
            );
            assert!(open_orders == open_orders_cmp, 0);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        // reset pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(5000000, 2500000, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 10000;
            let alice_deposit_USDC: u64 = 10000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 1000, 1000, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 10 * FLOAT_SCALING, 10000, 10000, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        // test list_open_orders before match
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let open_orders = list_open_orders(&pool, &account_cap);
            let mut open_orders_cmp = vector::empty<Order>();
            vector::push_back(
                &mut open_orders_cmp,
                clob::test_construct_order(0, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, true, account_cap_user)
            );
            vector::push_back(
                &mut open_orders_cmp,
                clob::test_construct_order(1, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, true, account_cap_user)
            );
            vector::push_back(
                &mut open_orders_cmp,
                clob::test_construct_order(2, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 1000, 1000, true, account_cap_user)
            );
            vector::push_back(
                &mut open_orders_cmp,
                clob::test_construct_order(0, CLIENT_ID_ALICE, 10 * FLOAT_SCALING, 10000, 10000, false, account_cap_user)
            );
            assert!(open_orders == open_orders_cmp, 0);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        // test match (ask side)
        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let (base_quantity_filled, quote_quantity_filled) = clob::test_match_ask(
                &mut pool,
                &account_cap,
                CLIENT_ID_BOB,
                1500,
                MIN_PRICE,
                0,
            );
            assert!(base_quantity_filled == 1500, 0);
            assert!(quote_quantity_filled == 6000 - 13 - 13 - 5, 0);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(bob, account_cap);
        };

        // test list_open_orders after match
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let open_orders = list_open_orders(&pool, &account_cap);
            let mut open_orders_cmp = vector::empty<Order>();
            vector::push_back(
                &mut open_orders_cmp,
                clob::test_construct_order(2, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 1000, 500, true, account_cap_user)
            );
            vector::push_back(
                &mut open_orders_cmp,
                clob::test_construct_order(0, CLIENT_ID_ALICE, 10 * FLOAT_SCALING, 10000, 10000, false, account_cap_user)
            );
            assert!(open_orders == open_orders_cmp, 0);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        end(test)
    }

        fun test_list_open_orders_empty_(mut test: Scenario): TransactionEffects {
        let (alice, _) = people();
        let owner = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(5000000, 2500000, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 10000;
            let alice_deposit_USDC: u64 = 10000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        // test list_open_orders
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let open_orders = list_open_orders(&pool, &account_cap);
            let open_orders_cmp = vector::empty<Order>();
            assert!(open_orders == open_orders_cmp, 0);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        end(test)
    }

    fun test_deposit_withdraw_(mut test: Scenario): TransactionEffects {
        let (alice, _) = people();
        let owner: address = @0xF;
        next_tx(&mut test, owner);
        {
            clob::setup_test(0, 0, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let alice_deposit_WSUI: u64 = 10000;
            let alice_withdraw_WSUI: u64 = 5000;
            let alice_deposit_USDC: u64 = 10000;
            let alice_withdraw_USDC: u64 = 1000;
            clob::deposit_base(&mut pool, mint_for_testing<SUI>(alice_deposit_WSUI, ctx(&mut test)), &account_cap);
            clob::deposit_quote(&mut pool, mint_for_testing<USD>(alice_deposit_USDC, ctx(&mut test)), &account_cap);
            burn_for_testing(clob::withdraw_base(&mut pool, alice_withdraw_WSUI, &account_cap, ctx(&mut test)));
            burn_for_testing(clob::withdraw_quote(&mut pool, alice_withdraw_USDC, &account_cap, ctx(&mut test)));
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            custodian::assert_user_balance(
                base_custodian,
                account_cap_user,
                alice_deposit_WSUI - alice_withdraw_WSUI,
                0
            );
            custodian::assert_user_balance(
                quote_custodian,
                account_cap_user,
                alice_deposit_USDC - alice_withdraw_USDC,
                0
            );
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        end(test)
    }

    fun test_batch_cancel_(mut test: Scenario): TransactionEffects {
        let (alice, _) = people();
        // setup pool and custodian
        let owner: address = @0xF;
        next_tx(&mut test, owner);
        {
            clob::setup_test(0, 0, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 10000;
            let alice_deposit_USDC: u64 = 10000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);

            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 1000, 1000, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 10 * FLOAT_SCALING, 10000, 10000, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (next_bid_order_id, next_ask_order_id, _, _) = clob::get_pool_stat(&pool);
            assert!(next_bid_order_id == clob::order_id_for_test(3, true), 0);
            assert!(next_ask_order_id == clob::order_id_for_test(1, false), 0);

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, true, account_cap_user)
                );
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(1, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, true, account_cap_user)
                );
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_tick_level(bids, 5 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(2, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 1000, 1000, true, account_cap_user)
                );
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_tick_level(bids, 2 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 10 * FLOAT_SCALING, 10000, 10000, false, account_cap_user)
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 10 * FLOAT_SCALING, &open_orders);
            };
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let mut orders = vector::empty<u64>();
            vector::push_back(&mut orders, 1);
            vector::push_back(&mut orders, 2);
            vector::push_back(&mut orders, MIN_ASK_ORDER_ID);
            clob::batch_cancel_order(&mut pool, orders, &account_cap);
            {
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_empty_tick_level(bids, 5 * FLOAT_SCALING);
            };
            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(2, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 1000, 1000, true, account_cap_user)
                );
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_tick_level(bids, 2 * FLOAT_SCALING, &open_orders);
            };
            {
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_empty_tick_level(asks, 10 * FLOAT_SCALING);
            };

            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        end(test)
    }

    fun test_clean_up_expired_orders_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();

        // setup pool and custodian
        let owner: address = @0xF;
        next_tx(&mut test, owner);
        {
            clob::setup_test(0, 0, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 10000;
            let alice_deposit_USDC: u64 = 110000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);

            clob::test_inject_limit_order_with_expiration(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, true,
                CANCEL_OLDEST, 0, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order_with_expiration(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, true,
                CANCEL_OLDEST, 0, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order_with_expiration(&mut pool, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 1000, 1000, true,
                CANCEL_OLDEST, 0, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order_with_expiration(&mut pool, CLIENT_ID_ALICE, 10 * FLOAT_SCALING, 10000, 10000, true,
                CANCEL_OLDEST, 0, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order_with_expiration(&mut pool, CLIENT_ID_ALICE, 11 * FLOAT_SCALING, 10000, 10000, false,
                CANCEL_OLDEST, 0, &account_cap, ctx(&mut test));
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            clob::check_balance_invariants_for_account(&account_cap, quote_custodian, base_custodian, &pool);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let bob_deposit_WSUI: u64 = 20000;
            let bob_deposit_USDC: u64 = 35000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, bob_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, bob_deposit_USDC);

            clob::test_inject_limit_order_with_expiration(&mut pool, CLIENT_ID_BOB, 11 * FLOAT_SCALING, 500, 500, false,
                CANCEL_OLDEST, 0, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order_with_expiration(&mut pool, CLIENT_ID_BOB, 12 * FLOAT_SCALING, 500, 500, false,
                CANCEL_OLDEST, 0, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order_with_expiration(&mut pool, CLIENT_ID_BOB, 13 * FLOAT_SCALING, 1000, 1000, false,
                CANCEL_OLDEST, 0, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order_with_expiration(&mut pool, CLIENT_ID_BOB, 14 * FLOAT_SCALING, 5000, 5000, false,
                CANCEL_OLDEST, 0, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order_with_expiration(&mut pool, CLIENT_ID_BOB, 5 * FLOAT_SCALING, 5000, 5000, true,
                CANCEL_OLDEST, 0, &account_cap, ctx(&mut test));
            test::return_shared(pool);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        next_tx(&mut test, bob);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            clob::check_balance_invariants_for_account(&account_cap, quote_custodian, base_custodian, &pool);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        next_tx(&mut test, owner);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap_alice = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_owner_alice = account_owner(&account_cap_alice);
            let account_cap_bob = test::take_from_address<AccountCap>(&test, bob);
            let account_cap_owner_bob = account_owner(&account_cap_bob);
            let mut clock = test::take_shared<Clock>(&test);
            clock::increment_for_testing(&mut clock, 1);
            let order_ids = vector<u64>[order_id_for_test(0, true), order_id_for_test(1, true), order_id_for_test(2, true), order_id_for_test(3, true), order_id_for_test(0, false)];
            let order_owners = vector<address>[account_cap_owner_alice, account_cap_owner_alice, account_cap_owner_alice, account_cap_owner_alice, account_cap_owner_alice];
            clob::clean_up_expired_orders(&mut pool, &clock, order_ids, order_owners);
            let (_, _, bids, _) = get_pool_stat(&pool);
            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(4, CLIENT_ID_BOB, 5 * FLOAT_SCALING, 5000, 5000, true, account_cap_owner_bob)
                );
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_tick_level(bids, 5 * FLOAT_SCALING, &open_orders);
            };
            clob::check_empty_tick_level(bids, 2 * FLOAT_SCALING);
            clob::check_empty_tick_level(bids, 10 * FLOAT_SCALING);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_owner_alice, 10000, 0);
            custodian::assert_user_balance<USD>(quote_custodian, account_cap_owner_alice, 110000, 0);

            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(alice, account_cap_alice);
            test::return_to_address<AccountCap>(bob, account_cap_bob);
        };
        next_tx(&mut test, owner);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let clock = test::take_shared<Clock>(&test);
            let account_cap_bob = test::take_from_address<AccountCap>(&test, bob);
            let account_cap_owner_bob = account_owner(&account_cap_bob);
            let order_ids = vector<u64>[order_id_for_test(1, false), order_id_for_test(2, false), order_id_for_test(3, false), order_id_for_test(4, false), order_id_for_test(4, true)];
            let order_owners = vector<address>[account_cap_owner_bob, account_cap_owner_bob, account_cap_owner_bob, account_cap_owner_bob, account_cap_owner_bob];
            clob::clean_up_expired_orders(&mut pool, &clock, order_ids, order_owners);
            let (_, _, _, asks) = get_pool_stat(&pool);
            clob::check_empty_tick_level(asks, 11 * FLOAT_SCALING);
            clob::check_empty_tick_level(asks, 12 * FLOAT_SCALING);
            clob::check_empty_tick_level(asks, 13 * FLOAT_SCALING);
            clob::check_empty_tick_level(asks, 14 * FLOAT_SCALING);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_owner_bob, 20000, 0);
            custodian::assert_user_balance<USD>(quote_custodian, account_cap_owner_bob, 35000, 0);

            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(bob, account_cap_bob);
        };
        end(test)
    }

    fun test_partial_fill_and_cancel_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        let owner: address = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(0, 0, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_sender<AccountCap>(&test);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            custodian::deposit(
                base_custodian,
                mint_for_testing<SUI>(1000 * 100000000, ctx(&mut test)),
                account_cap_user
            );
            custodian::deposit(
                quote_custodian,
                mint_for_testing<USD>(10000 * 100000000, ctx(&mut test)),
                account_cap_user
            );
            test::return_shared(pool);
            test::return_to_sender<AccountCap>(&test, account_cap);
        };

        // alice places limit orders
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_sender<AccountCap>(&test);
            let clock = test::take_shared<Clock>(&test);
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                5 * FLOAT_SCALING,
                200 * 100000000,
                CANCEL_OLDEST,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                4 * FLOAT_SCALING,
                200 * 100000000,
                CANCEL_OLDEST,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                4 * FLOAT_SCALING,
                200 * 100000000,
                CANCEL_OLDEST,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                10 * FLOAT_SCALING,
                1000 * 100000000,
                CANCEL_OLDEST,
                false,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            let (next_bid_order_id, next_ask_order_id, _, _) = clob::get_pool_stat(&pool);
            assert!(next_bid_order_id == clob::order_id_for_test(3, true), 0);
            assert!(next_ask_order_id == clob::order_id_for_test(1, false), 0);
            test::return_shared(clock);
            test::return_shared(pool);
            test::return_to_sender<AccountCap>(&test, account_cap);
        };
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            clob::check_balance_invariants_for_account(&account_cap, quote_custodian, base_custodian, &pool);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_sender<AccountCap>(&test);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user, 7400 * 100000000, 2600 * 100000000);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user, 0, 1000 * 100000000);
            test::return_shared(pool);
            test::return_to_sender<AccountCap>(&test, account_cap);
        };
        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, _) = clob::borrow_mut_custodian(&mut pool);
            custodian::deposit(
                base_custodian,
                mint_for_testing<SUI>(300 * 100000000, ctx(&mut test)),
                account_cap_user
            );
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user, 300 * 100000000, 0);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(bob, account_cap);
        };

        // bob places market order
        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_sender<AccountCap>(&test);
            let clock = test::take_shared<Clock>(&test);
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_BOB,
                4 * FLOAT_SCALING,
                300 * 100000000,
                CANCEL_OLDEST,
                false,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            test::return_shared(clock);
            test::return_shared(pool);
            test::return_to_sender<AccountCap>(&test, account_cap);
        };
        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user, 0, 0);
            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user, 1400 * 100000000, 0);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(bob, account_cap);
        };

        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            {
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_empty_tick_level(bids, 5 * FLOAT_SCALING);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(1, CLIENT_ID_ALICE, 4 * FLOAT_SCALING, 100 * 100000000, 100 * 100000000, true, account_cap_user)
                );
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(2, CLIENT_ID_ALICE, 4 * FLOAT_SCALING, 200 * 100000000, 200 * 100000000, true, account_cap_user)
                );
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_tick_level(bids, 4 * FLOAT_SCALING, &open_orders);
            };

            clob::cancel_order<SUI, USD>(&mut pool, 2, &account_cap);
            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(2, CLIENT_ID_ALICE, 4 * FLOAT_SCALING, 200 * 100000000, 200 * 100000000, true, account_cap_user)
                );
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_tick_level(bids, 4 * FLOAT_SCALING, &open_orders);
            };

            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        end(test)
    }

    fun test_full_transaction_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        let owner: address = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(5000000, 2500000, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_sender<AccountCap>(&test);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            custodian::deposit(base_custodian, mint_for_testing<SUI>(10000, ctx(&mut test)), account_cap_user);
            custodian::deposit(quote_custodian, mint_for_testing<USD>(100000, ctx(&mut test)), account_cap_user);
            test::return_shared(pool);
            test::return_to_sender<AccountCap>(&test, account_cap);
        };

        // alice places limit orders
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_sender<AccountCap>(&test);
            let clock = test::take_shared<Clock>(&test);
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                5 * FLOAT_SCALING,
                2000,
                CANCEL_OLDEST,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                5 * FLOAT_SCALING,
                3000,
                CANCEL_OLDEST,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                2 * FLOAT_SCALING,
                10000,
                CANCEL_OLDEST,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                20 * FLOAT_SCALING,
                10000,
                CANCEL_OLDEST,
                false,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            let (next_bid_order_id, next_ask_order_id, _, _) = clob::get_pool_stat(&pool);
            assert!(next_bid_order_id == clob::order_id_for_test(3, true), 0);
            assert!(next_ask_order_id == clob::order_id_for_test(1, false), 0);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            custodian::assert_user_balance(base_custodian, account_cap_user, 0, 10000);
            custodian::assert_user_balance(quote_custodian, account_cap_user, 55000, 45000);
            let (base_avail, base_locked, quote_avail, quote_locked) = account_balance(&pool, &account_cap);
            assert!(base_avail == 0, 0);
            assert!(base_locked == 10000, 0);
            assert!(quote_avail == 55000, 0);
            assert!(quote_locked == 45000, 0);
            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            clob::check_balance_invariants_for_account(&account_cap, quote_custodian, base_custodian, &pool);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        // bob places market order
        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let clock = test::take_shared<Clock>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let (coin1, coin2) = clob::place_market_order<SUI, USD>(&mut pool, &account_cap, CLIENT_ID_BOB, 6000,
                false,
                mint_for_testing<SUI>(6000, ctx(&mut test)),
                mint_for_testing<USD>(0, ctx(&mut test)),
                &clock,
                ctx(&mut test));
            assert!(coin::value<SUI>(&coin1) == 0, 0);
            assert!(coin::value<USD>(&coin2) == 27000 - 135, 0);
            burn_for_testing(coin1);
            burn_for_testing(coin2);
            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(bob, account_cap);
        };

        // bob passes in 600sui, and sells 100sui of it through market ask order
        // Bob should receive the remaining 500sui,
        // and 199 usdt (excluding handling fee) for selling 100sui at a unit price of 2
        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let clock = test::take_shared<Clock>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let (coin1, coin2) =clob::place_market_order<SUI, USD>(&mut pool, &account_cap, CLIENT_ID_BOB, 1000,
                false,
                mint_for_testing<SUI>(6000, ctx(&mut test)),
                mint_for_testing<USD>(0, ctx(&mut test)),
                &clock,
                ctx(&mut test));
            assert!(coin::value<SUI>(&coin1) == 5000, 0);
            assert!(coin::value<USD>(&coin2) == 1990, 0);
            burn_for_testing(coin1);
            burn_for_testing(coin2);
            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        end(test)
    }

    fun test_place_limit_order_fill_or_kill_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        let owner: address = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(5000000, 2500000, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };

        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_sender<AccountCap>(&test);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            custodian::deposit(base_custodian, mint_for_testing<SUI>(10000, ctx(&mut test)), account_cap_user);
            custodian::deposit(quote_custodian, mint_for_testing<USD>(100000, ctx(&mut test)), account_cap_user);
            test::return_shared(pool);
            test::return_to_sender<AccountCap>(&test, account_cap);
        };

        // alice places limit orders
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let clock = test::take_shared<Clock>(&test);
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                5 * FLOAT_SCALING,
                2000,
                CANCEL_OLDEST,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                5 * FLOAT_SCALING,
                3000,
                CANCEL_OLDEST,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                2 * FLOAT_SCALING,
                10000,
                CANCEL_OLDEST,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                20 * FLOAT_SCALING,
                10000,
                CANCEL_OLDEST,
                false,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            let (next_bid_order_id, next_ask_order_id, _, _) = clob::get_pool_stat(&pool);
            assert!(next_bid_order_id == clob::order_id_for_test(3, true), 0);
            assert!(next_ask_order_id == clob::order_id_for_test(1, false), 0);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            custodian::assert_user_balance(base_custodian, account_cap_user, 0, 10000);
            custodian::assert_user_balance(quote_custodian, account_cap_user, 55000, 45000);
            let (base_avail, base_locked, quote_avail, quote_locked) = account_balance(&pool, &account_cap);
            assert!(base_avail == 0, 0);
            assert!(base_locked == 10000, 0);
            assert!(quote_avail == 55000, 0);
            assert!(quote_locked == 45000, 0);
            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_sender<AccountCap>(&test);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            custodian::deposit(base_custodian, mint_for_testing<SUI>(10000, ctx(&mut test)), account_cap_user);
            custodian::deposit(quote_custodian, mint_for_testing<USD>(100000, ctx(&mut test)), account_cap_user);
            test::return_shared(pool);
            test::return_to_sender<AccountCap>(&test, account_cap);
        };

        // bob places limit order of FILL_OR_KILL
        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_sender<AccountCap>(&test);
            let clock = test::take_shared<Clock>(&test);
            let (base_quantity_filled, quote_quantity_filled, is_placed, order_id) = clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_BOB,
                4 * FLOAT_SCALING,
                4000,
                CANCEL_OLDEST,
                false,
                TIMESTAMP_INF,
                FILL_OR_KILL,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            assert!(base_quantity_filled == 4000, 0);
            assert!(quote_quantity_filled == 19900, 0);
            assert!(is_placed == false, 0);
            assert!(order_id == 0, 0);

            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(bob, account_cap);
        };

        // check bob's balance after the limit order is matched
        next_tx(&mut test, bob);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_sender<AccountCap>(&test);
            let clock = test::take_shared<Clock>(&test);

            let  (base_avail, base_locked, quote_avail, quote_locked) = account_balance<SUI, USD>(&pool, &account_cap);
            assert!(base_avail == 6000, 0);
            assert!(base_locked == 0, 0);
            assert!(quote_avail == 119900, 0);
            assert!(quote_locked == 0, 0);

            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        end(test)
    }

    fun test_place_limit_order_post_or_abort_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        let owner: address = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(5000000, 2500000, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };

        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_sender<AccountCap>(&test);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            custodian::deposit(base_custodian, mint_for_testing<SUI>(10000, ctx(&mut test)), account_cap_user);
            custodian::deposit(quote_custodian, mint_for_testing<USD>(100000, ctx(&mut test)), account_cap_user);
            test::return_shared(pool);
            test::return_to_sender<AccountCap>(&test, account_cap);
        };

        // alice places limit orders
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let clock = test::take_shared<Clock>(&test);
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                5 * FLOAT_SCALING,
                2000,
                CANCEL_OLDEST,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                5 * FLOAT_SCALING,
                3000,
                CANCEL_OLDEST,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                2 * FLOAT_SCALING,
                10000,
                CANCEL_OLDEST,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                20 * FLOAT_SCALING,
                10000,
                CANCEL_OLDEST,
                false,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            let (next_bid_order_id, next_ask_order_id, _, _) = clob::get_pool_stat(&pool);
            assert!(next_bid_order_id == clob::order_id_for_test(3, true), 0);
            assert!(next_ask_order_id == clob::order_id_for_test(1, false), 0);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            custodian::assert_user_balance(base_custodian, account_cap_user, 0, 10000);
            custodian::assert_user_balance(quote_custodian, account_cap_user, 55000, 45000);
            let (base_avail, base_locked, quote_avail, quote_locked) = account_balance(&pool, &account_cap);
            assert!(base_avail == 0, 0);
            assert!(base_locked == 10000, 0);
            assert!(quote_avail == 55000, 0);
            assert!(quote_locked == 45000, 0);
            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_sender<AccountCap>(&test);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            custodian::deposit(base_custodian, mint_for_testing<SUI>(10000, ctx(&mut test)), account_cap_user);
            custodian::deposit(quote_custodian, mint_for_testing<USD>(100000, ctx(&mut test)), account_cap_user);
            test::return_shared(pool);
            test::return_to_sender<AccountCap>(&test, account_cap);
        };

        // bob places limit order of POST OR ABORT
        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_sender<AccountCap>(&test);
            let clock = test::take_shared<Clock>(&test);
            let (base_quantity_filled, quote_quantity_filled, is_placed, order_id) = clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_BOB,
                6 * FLOAT_SCALING,
                4000,
                CANCEL_OLDEST,
                false,
                TIMESTAMP_INF,
                POST_OR_ABORT,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            assert!(base_quantity_filled == 0, 0);
            assert!(quote_quantity_filled == 0, 0);
            assert!(is_placed == true, 0);
            assert!(order_id == MIN_ASK_ORDER_ID + 1, 0);

            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(bob, account_cap);
        };

        // check bob's balance
        next_tx(&mut test, bob);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_sender<AccountCap>(&test);
            let clock = test::take_shared<Clock>(&test);

            let  (base_avail, base_locked, quote_avail, quote_locked) = account_balance<SUI, USD>(&pool, &account_cap);
            assert!(base_avail == 6000, 0);
            assert!(base_locked == 4000, 0);
            assert!(quote_avail == 100000, 0);
            assert!(quote_locked == 0, 0);

            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        end(test)
    }

    fun test_absorb_all_liquidity_bid_side_with_customized_tick_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        // setup pool and custodian
        let owner: address = @0xF;
        next_tx(&mut test, owner);
        {
            clob::setup_test_with_tick_min(5000000, 2500000, 1_00_000_000, 10, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_sender<AccountCap>(&test);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            custodian::deposit(base_custodian, mint_for_testing<SUI>(10000, ctx(&mut test)), account_cap_user);
            custodian::deposit(quote_custodian, mint_for_testing<USD>(100000, ctx(&mut test)), account_cap_user);
            test::return_shared(pool);
            test::return_to_sender<AccountCap>(&test, account_cap);
        };

        // alice places limit orders
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let clock = test::take_shared<Clock>(&test);
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                5 * FLOAT_SCALING,
                2000,
                CANCEL_OLDEST,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                5 * FLOAT_SCALING,
                3000,
                CANCEL_OLDEST,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                2 * FLOAT_SCALING,
                10000,
                CANCEL_OLDEST,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                20 * FLOAT_SCALING,
                10000,
                CANCEL_OLDEST,
                false,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            let (next_bid_order_id, next_ask_order_id, _, _) = clob::get_pool_stat(&pool);
            assert!(next_bid_order_id == clob::order_id_for_test(3, true), 0);
            assert!(next_ask_order_id == clob::order_id_for_test(1, false), 0);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            custodian::assert_user_balance(base_custodian, account_cap_user, 0, 10000);
            custodian::assert_user_balance(quote_custodian, account_cap_user, 55000, 45000);
            let (base_avail, base_locked, quote_avail, quote_locked) = account_balance(&pool, &account_cap);
            assert!(base_avail == 0, 0);
            assert!(base_locked == 10000, 0);
            assert!(quote_avail == 55000, 0);
            assert!(quote_locked == 45000, 0);
            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        // bob places market order
        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let clock = test::take_shared<Clock>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let (coin1, coin2) = clob::place_market_order<SUI, USD>(&mut pool, &account_cap, CLIENT_ID_BOB, 20000, false,
                mint_for_testing<SUI>(20000, ctx(&mut test)),
                mint_for_testing<USD>(0, ctx(&mut test)),
                &clock,
                ctx(&mut test));
            assert!(coin::value<SUI>(&coin1) == 5000, 0);
            assert!(coin::value<USD>(&coin2) == 44775, 0);
            burn_for_testing(coin1);
            burn_for_testing(coin2);
            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        end(test)
    }

    fun test_absorb_all_liquidity_ask_side_with_customized_tick_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        let owner: address = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test_with_tick_min(5000000, 2500000, 1_00_000_000, 10, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_sender<AccountCap>(&test);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            custodian::deposit(base_custodian, mint_for_testing<SUI>(100000, ctx(&mut test)), account_cap_user);
            custodian::deposit(quote_custodian, mint_for_testing<USD>(100000, ctx(&mut test)), account_cap_user);
            test::return_shared(pool);
            test::return_to_sender<AccountCap>(&test, account_cap);
        };

        // alice places limit orders
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let clock = test::take_shared<Clock>(&test);
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                5 * FLOAT_SCALING,
                5000,
                CANCEL_OLDEST,
                false,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                5 * FLOAT_SCALING,
                5000,
                CANCEL_OLDEST,
                false,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                2 * FLOAT_SCALING,
                10000,
                CANCEL_OLDEST,
                false,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                1 * FLOAT_SCALING,
                10000,
                CANCEL_OLDEST,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            let (next_bid_order_id, next_ask_order_id, _, _) = clob::get_pool_stat(&pool);
            assert!(next_bid_order_id == clob::order_id_for_test(1, true), 0);
            assert!(next_ask_order_id == clob::order_id_for_test(3, false), 0);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            custodian::assert_user_balance(base_custodian, account_cap_user, 80000, 20000);
            custodian::assert_user_balance(quote_custodian, account_cap_user, 90000, 10000);
            let (base_avail, base_locked, quote_avail, quote_locked) = account_balance(&pool, &account_cap);
            assert!(base_avail == 80000, 0);
            assert!(base_locked == 20000, 0);
            assert!(quote_avail == 90000, 0);
            assert!(quote_locked == 10000, 0);
            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        // bob places market order
        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let clock = test::take_shared<Clock>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let (coin1, coin2) = clob::place_market_order<SUI, USD>(&mut pool, &account_cap, CLIENT_ID_BOB, 50000, true,
                mint_for_testing<SUI>(100000, ctx(&mut test)),
                mint_for_testing<USD>(100000, ctx(&mut test)),
                &clock,
                ctx(&mut test));
            assert!(coin::value<SUI>(&coin1) == 120000, 0);
            assert!(coin::value<USD>(&coin2) == 100000 - (70000 + 350), 0);
            burn_for_testing(coin1);
            burn_for_testing(coin2);
            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        end(test)
    }

    fun test_swap_exact_quote_for_base_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        let owner = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(5000000, 2500000, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 100000;
            let alice_deposit_USDC: u64 = 100000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 5000, 5000, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 5000, 5000, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 10000, 10000, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE,1 * FLOAT_SCALING, 100000, 100000, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));

            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let clock = test::take_shared<Clock>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let (base_coin, quote_coin, _) = clob::swap_exact_quote_for_base(
                &mut pool,
                CLIENT_ID_BOB,
                &account_cap,
                45000,
                &clock,
                mint_for_testing<USD>(45000, ctx(&mut test)),
                ctx(&mut test)
            );
            assert!(coin::value(&base_coin) == 10000 + 4000, 0);
            assert!(coin::value(&quote_coin) == 4800, 0);
            burn_for_testing(base_coin);
            burn_for_testing(quote_coin);

            // Check Alice for invariants
            let alice_account_cap = test::take_from_address<AccountCap>(&test, alice);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            clob::check_balance_invariants_for_account(&alice_account_cap, quote_custodian, base_custodian, &pool);
            test::return_shared(clock);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(bob, account_cap);
            test::return_to_address<AccountCap>(alice, alice_account_cap);
        };
        end(test)
    }

    fun test_swap_exact_base_for_quote_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        let owner = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(5000000, 2500000, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 100000;
            let alice_deposit_USDC: u64 = 100000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE,5 * FLOAT_SCALING, 5000, 5000, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE,5 * FLOAT_SCALING, 5000, 5000, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE,2 * FLOAT_SCALING, 10000, 10000, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE,10 * FLOAT_SCALING, 100000, 100000, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let clock = test::take_shared<Clock>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let (base_coin, quote_coin, _) = clob::swap_exact_base_for_quote(
                &mut pool,
                CLIENT_ID_BOB,
                &account_cap,
                15000,
                mint_for_testing<SUI>(15000, ctx(&mut test)),
                mint_for_testing<USD>(0,  ctx(&mut test)),
                &clock,
                ctx(&mut test)
            );
            let alice_account_cap = test::take_from_address<AccountCap>(&test, alice);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            clob::check_balance_invariants_for_account(&alice_account_cap, quote_custodian, base_custodian, &pool);

            assert!(coin::value(&base_coin) == 0, 0);
            assert!(coin::value(&quote_coin) == 59700, 0);
            burn_for_testing(base_coin);
            burn_for_testing(quote_coin);

            test::return_shared(clock);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, alice_account_cap);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        end(test)
    }

    fun test_withdraw_fees_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        let owner = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(250000, 150000, &mut test, owner);
        };
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 1000000000;
            let alice_deposit_USDC: u64 = 1000000000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            // Example selling 0.1 sui, for the price of .719
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 719000, 1000000000, 1000000000, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));

            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);

            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            clob::check_balance_invariants_for_account(&account_cap, quote_custodian, base_custodian, &pool);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, bob);
        // Buys some sui from alice
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let clock = test::take_shared<Clock>(&test);

            let (base_coin, quote_coin, _) = clob::swap_exact_base_for_quote(
                &mut pool,
                CLIENT_ID_BOB,
                &account_cap,
                100000,
                mint_for_testing<SUI>(100000000, ctx(&mut test)),
                mint_for_testing<USD>(0,  ctx(&mut test)),
                &clock,
                ctx(&mut test)
            );

            burn_for_testing(base_coin);
            burn_for_testing(quote_coin);

            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            clob::check_balance_invariants_for_account(&account_cap, quote_custodian, base_custodian, &pool);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        // Alice cancels orders
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (_, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let(asset_avail, asset_locked) = custodian::account_balance(quote_custodian, account_cap_user);
            clob::cancel_order(&mut pool, 1, &account_cap);

            let (_, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let(asset_avail_after, asset_locked_after) = custodian::account_balance(quote_custodian, account_cap_user);

            // Assert locked balance is 0 and the new balance is equal to the sum
            assert!(asset_locked_after == 0, 0);
            assert!(asset_avail_after == (asset_avail + asset_locked), 0);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        next_tx(&mut test, owner);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let pool_cap = test::take_from_address<PoolOwnerCap>(&test, owner);
            let fees = clob::withdraw_fees(&pool_cap, &mut pool, test::ctx(&mut test));
            let amount = coin::burn_for_testing(fees);

            assert!(amount > 0, 0);

            test::return_shared(pool);
            test::return_to_address<PoolOwnerCap>(owner, pool_cap);
        };

        end(test)
    }

    fun test_withdraw_fees_with_incorrect_pool_owner_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        let owner = @0xF;
        // setup pool and custodian

        next_tx(&mut test, owner);
        clob::setup_test(250000, 150000, &mut test, alice);

        next_tx(&mut test, owner);
        clob::setup_test(250000, 150000, &mut test, owner);

        mint_account_cap_transfer(alice, test::ctx(&mut test));

        next_tx(&mut test, bob);
        mint_account_cap_transfer(bob, test::ctx(&mut test));

        next_tx(&mut test, alice); {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 1000000000;
            let alice_deposit_USDC: u64 = 1000000000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            // Example selling 0.1 sui, for the price of .719
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 719000, 1000000000, 1000000000, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));

            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        next_tx(&mut test, alice); {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);

            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            clob::check_balance_invariants_for_account(&account_cap, quote_custodian, base_custodian, &pool);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        // Buys some sui from alice
        next_tx(&mut test, bob); {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let clock = test::take_shared<Clock>(&test);

            let (base_coin, quote_coin, _) = clob::swap_exact_base_for_quote(
                &mut pool,
                CLIENT_ID_BOB,
                &account_cap,
                100000,
                mint_for_testing<SUI>(100000000, ctx(&mut test)),
                mint_for_testing<USD>(0,  ctx(&mut test)),
                &clock,
                ctx(&mut test)
            );

            burn_for_testing(base_coin);
            burn_for_testing(quote_coin);

            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(bob, account_cap);
        };

        next_tx(&mut test, alice); {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            clob::check_balance_invariants_for_account(&account_cap, quote_custodian, base_custodian, &pool);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        // Alice cancels orders
        next_tx(&mut test, alice); {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (_, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let(asset_avail, asset_locked) = custodian::account_balance(quote_custodian, account_cap_user);
            clob::cancel_order(&mut pool, 1, &account_cap);

            let (_, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let(asset_avail_after, asset_locked_after) = custodian::account_balance(quote_custodian, account_cap_user);

            // Assert locked balance is 0 and the new balance is equal to the sum
            assert!(asset_locked_after == 0, 0);
            assert!(asset_avail_after == (asset_avail + asset_locked), 0);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        next_tx(&mut test, owner); {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let pool_cap = test::take_from_address<PoolOwnerCap>(&test, alice);
            let fees = clob::withdraw_fees(&pool_cap, &mut pool, test::ctx(&mut test));
            let _ = coin::burn_for_testing(fees);

            abort 1337
        }
    }

    fun test_pool_with_small_fee_example_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        let owner = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(250000, 150000, &mut test, owner);
        };
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 1000000000;
            let alice_deposit_USDC: u64 = 1000000000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            // Example selling 0.1 sui, for the price of .719
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 719000, 1000000000, 1000000000, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));

            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);

            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            clob::check_balance_invariants_for_account(&account_cap, quote_custodian, base_custodian, &pool);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, bob);
        // Buys some sui from alice
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let clock = test::take_shared<Clock>(&test);

            let (base_coin, quote_coin, _) = clob::swap_exact_base_for_quote(
                &mut pool,
                CLIENT_ID_BOB,
                &account_cap,
                100000,
                mint_for_testing<SUI>(100000000, ctx(&mut test)),
                mint_for_testing<USD>(0,  ctx(&mut test)),
                &clock,
                ctx(&mut test)
            );

            burn_for_testing(base_coin);
            burn_for_testing(quote_coin);

            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            clob::check_balance_invariants_for_account(&account_cap, quote_custodian, base_custodian, &pool);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        // Alice cancels orders
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (_, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let(asset_avail, asset_locked) = custodian::account_balance(quote_custodian, account_cap_user);
            clob::cancel_order(&mut pool, 1, &account_cap);

            let (_, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let(asset_avail_after, asset_locked_after) = custodian::account_balance(quote_custodian, account_cap_user);

            // Assert locked balance is 0 and the new balance is equal to the sum
            assert!(asset_locked_after == 0, 0);
            assert!(asset_avail_after == (asset_avail + asset_locked), 0);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        next_tx(&mut test, owner);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let pool_cap = test::take_from_address<PoolOwnerCap>(&test, owner);
            let fees = clob::withdraw_fees(&pool_cap, &mut pool, test::ctx(&mut test));
            let amount = coin::burn_for_testing(fees);

            assert!(amount > 0, 0);

            test::return_shared(pool);
            test::return_to_address<PoolOwnerCap>(owner, pool_cap);
        };

        end(test)
    }

    fun test_cancel_and_remove_(mut test: Scenario): TransactionEffects {
        let (alice, _) = people();
        let owner: address = @0xF;
        next_tx(&mut test, owner);
        {
            clob::setup_test(0, 0, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 10;
            let alice_deposit_USDC: u64 = 100;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);

            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 2, 2, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 3, 3, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 10, 10, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 10, 10, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 20 * FLOAT_SCALING, 10, 10, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 2, 2, true, account_cap_user)
                );
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(1, CLIENT_ID_ALICE,5 * FLOAT_SCALING, 3, 3, true, account_cap_user)
                );
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_tick_level(bids, 5 * FLOAT_SCALING, &open_orders);
            };
            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(2, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 10, 10, true, account_cap_user)
                );
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(3, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 10, 10, true, account_cap_user)
                );
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_tick_level(bids, 2 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 20 * FLOAT_SCALING, 10, 10, false, account_cap_user)
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 20 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 2, 2, true, account_cap_user)
                );
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(1, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 3, 3, true, account_cap_user)
                );
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_tick_level(bids, 5 * FLOAT_SCALING, &open_orders);
            };

            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user, 35, 65);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user, 0, 10);

            // check usr open orders before cancel
            {
                let mut usr_open_orders_cmp = vector::empty<u64>();
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(0, true));
                vector::push_back(&mut usr_open_orders_cmp, 5 * FLOAT_SCALING);
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(1, true));
                vector::push_back(&mut usr_open_orders_cmp, 5 * FLOAT_SCALING);
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(2, true));
                vector::push_back(&mut usr_open_orders_cmp, 2 * FLOAT_SCALING);
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(3, true));
                vector::push_back(&mut usr_open_orders_cmp, 2 * FLOAT_SCALING);
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(0, false));
                vector::push_back(&mut usr_open_orders_cmp, 20 * FLOAT_SCALING);
                clob::check_usr_open_orders(clob::get_usr_open_orders(&pool, account_cap_user), &usr_open_orders_cmp);
            };
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            clob::cancel_order(&mut pool, 1, &account_cap);
            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(1, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 3, 3, true, account_cap_user)
                );
                // check tick level from pool after remove order
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_tick_level(bids, 5 * FLOAT_SCALING, &open_orders);
                // check usr open orders after remove order bid order of sequence_id 0
                let mut usr_open_orders_cmp = vector::empty<u64>();
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(0, false));
                vector::push_back(&mut usr_open_orders_cmp, 20 * FLOAT_SCALING);
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(1, true));
                vector::push_back(&mut usr_open_orders_cmp, 5 * FLOAT_SCALING);
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(2, true));
                vector::push_back(&mut usr_open_orders_cmp, 2 * FLOAT_SCALING);
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(3, true));
                vector::push_back(&mut usr_open_orders_cmp, 2 * FLOAT_SCALING);
                clob::check_usr_open_orders(clob::get_usr_open_orders(&pool, account_cap_user), &usr_open_orders_cmp);
            };
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        next_tx(&mut test, alice);
        {
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user, 35 + 10, 65 - 10);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user, 0, 10);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            clob::cancel_order(&mut pool, 2, &account_cap);
            {
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_empty_tick_level(bids, 5 * FLOAT_SCALING);
                let mut usr_open_orders_cmp = vector::empty<u64>();
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(0, false));
                vector::push_back(&mut usr_open_orders_cmp, 20 * FLOAT_SCALING);
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(3, true));
                vector::push_back(&mut usr_open_orders_cmp, 2 * FLOAT_SCALING);
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(2, true));
                vector::push_back(&mut usr_open_orders_cmp, 2 * FLOAT_SCALING);
                clob::check_usr_open_orders(clob::get_usr_open_orders(&pool, account_cap_user), &usr_open_orders_cmp);
            };
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user, 35 + 10 + 15, 65 - 10 - 15);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user, 0, 10);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            clob::cancel_order(&mut pool, MIN_ASK_ORDER_ID, &account_cap);
            {
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_empty_tick_level(asks, 20 * FLOAT_SCALING);
                let mut usr_open_orders_cmp = vector::empty<u64>();
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(3, true));
                vector::push_back(&mut usr_open_orders_cmp, 2 * FLOAT_SCALING);
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(2, true));
                vector::push_back(&mut usr_open_orders_cmp, 2 * FLOAT_SCALING);
                clob::check_usr_open_orders(clob::get_usr_open_orders(&pool, account_cap_user), &usr_open_orders_cmp);
            };
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user, 35 + 10 + 15, 65 - 10 - 15);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user, 10, 0);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        end(test)
    }

    fun test_inject_and_match_taker_bid_with_quote_quantity_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        let owner = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(5000000, 2500000, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let (base_quantity_filled, quote_quantity_filled) = clob::test_match_bid_with_quote_quantity<SUI, USD>(&mut pool, &account_cap, CLIENT_ID_BOB, 5000, MAX_PRICE, 0);
            assert_eq(base_quantity_filled, 0);
            assert_eq(quote_quantity_filled, 0);
            test::return_to_address<AccountCap>(bob, account_cap);
            test::return_shared(pool);
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 100000;
            let alice_deposit_USDC: u64 = 100000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 5000, 5000, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 5000, 5000, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE,  2 * FLOAT_SCALING, 10000, 10000, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE,  1 * FLOAT_SCALING, 100000, 100000, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        // test inject limit order and match (bid side)
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);

            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user, 0, 100000);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user, 80000, 20000);
            let (next_bid_order_id, next_ask_order_id, _, _) = clob::get_pool_stat(&pool);
            assert!(next_bid_order_id == clob::order_id_for_test(1, true), 0);
            assert!(next_ask_order_id == clob::order_id_for_test(3, false), 0);

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 5000, 5000, false, account_cap_user)
                );
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(1, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 5000, 5000, false, account_cap_user)
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 5 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(2, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 10000, 10000, false, account_cap_user)
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 2 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 1 * FLOAT_SCALING, 100000, 100000, true, account_cap_user)
                );
                let (_, _, bid, _) = get_pool_stat(&pool);
                clob::check_tick_level(bid, 1 * FLOAT_SCALING, &open_orders);
            };
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        // test match (bid side)
        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let (base_quantity_filled, quote_quantity_filled) = clob::test_match_bid_with_quote_quantity(
                &mut pool,
                &account_cap,
                CLIENT_ID_BOB,
                45000,
                MAX_PRICE,
                0,
            );
            assert!(base_quantity_filled == 10000 + 4000, 0);
            assert!(quote_quantity_filled == 40200, 0);
            let (base_quantity_filled, quote_quantity_filled) = clob::test_match_bid_with_quote_quantity(
                &mut pool,
                &account_cap,
                CLIENT_ID_BOB,
                5000,
                0,
                0,
            );
            assert_eq(base_quantity_filled, 0);
            assert_eq(quote_quantity_filled, 0);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        next_tx(&mut test, bob);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap_alice = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user_alice = account_owner(&account_cap_alice);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);

            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user_alice, 40200 - 100 - 100 + 50 + 50, 100000);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user_alice, 80000, 6000);
            {
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_empty_tick_level(asks, 2 * FLOAT_SCALING);
            };
            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE,  5 * FLOAT_SCALING, 5000, 1000, false, account_cap_user_alice)
                );
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(1, CLIENT_ID_ALICE,  5 * FLOAT_SCALING, 5000, 5000, false, account_cap_user_alice)
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 5 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 1 * FLOAT_SCALING, 100000, 100000, true, account_cap_user_alice)
                );
                let (_, _, bid, _) = get_pool_stat(&pool);
                clob::check_tick_level(bid, 1 * FLOAT_SCALING, &open_orders);
            };

            let open_orders = list_open_orders(&pool, &account_cap_alice);
            let mut open_orders_cmp = vector::empty<Order>();
            vector::push_back(
                &mut open_orders_cmp,
                clob::test_construct_order(0, CLIENT_ID_ALICE,  5 * FLOAT_SCALING, 5000, 1000, false, account_cap_user_alice)
            );
            vector::push_back(
                &mut open_orders_cmp,
                clob::test_construct_order(1, CLIENT_ID_ALICE,  5 * FLOAT_SCALING, 5000, 5000, false, account_cap_user_alice)
            );
            vector::push_back(
                &mut open_orders_cmp,
                clob::test_construct_order(0, CLIENT_ID_ALICE, 1 * FLOAT_SCALING, 100000, 100000, true, account_cap_user_alice)
            );
            assert!(open_orders == open_orders_cmp, 0);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap_alice);
        };

        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);

            let (base_quantity_filled, quote_quantity_filled) = clob::test_match_bid_with_quote_quantity(
                &mut pool,
               &account_cap,
                CLIENT_ID_BOB,
                40000,
                MAX_PRICE,
                0,
            );
            assert_eq(base_quantity_filled, 6000);
            assert_eq(quote_quantity_filled, 30150);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(bob, account_cap);
        };

        next_tx(&mut test, bob);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            {
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_empty_tick_level(asks, 2 * FLOAT_SCALING);
            };
            {
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_empty_tick_level(asks, 5 * FLOAT_SCALING);
            };

            test::return_shared(pool);
        };

        end(test)
    }

    fun test_inject_and_match_taker_bid_with_quote_quantity_zero_lot_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        let owner = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test_with_tick_min(5000000, 2500000, 1 * FLOAT_SCALING, 100, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 10000;
            let alice_deposit_USDC: u64 = 10000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 1000, 1000, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 1 * FLOAT_SCALING, 10000, 10000, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let (base_quantity_filled, quote_quantity_filled) = clob::test_match_bid_with_quote_quantity(
                &mut pool,
                &account_cap,
                CLIENT_ID_BOB,
                // needs 201 to fill 1 lot
                200,
                MAX_PRICE,
                0,
            );
            assert!(base_quantity_filled == 0, 0);
            assert!(quote_quantity_filled == 0, 0);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        next_tx(&mut test, bob);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap_alice = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user_alice = account_owner(&account_cap_alice);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);

            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user_alice, 0, 10000);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user_alice, 8000, 2000);
            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, false, account_cap_user_alice)
                );
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(1, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, false, account_cap_user_alice)
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 5 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(2, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 1000, 1000, false, account_cap_user_alice)
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 2 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 1 * FLOAT_SCALING, 10000, 10000, true, account_cap_user_alice)
                );
                let (_, _, bid, _) = get_pool_stat(&pool);
                clob::check_tick_level(bid, 1 * FLOAT_SCALING, &open_orders);
            };

            let open_orders = list_open_orders(&pool, &account_cap_alice);
            let mut open_orders_cmp = vector::empty<Order>();
            vector::push_back(
                &mut open_orders_cmp,
                clob::test_construct_order(0, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, false, account_cap_user_alice)
            );
            vector::push_back(
                &mut open_orders_cmp,
                clob::test_construct_order(1, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, false, account_cap_user_alice)
            );
            vector::push_back(
                &mut open_orders_cmp,
                clob::test_construct_order(2, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 1000, 1000, false, account_cap_user_alice)
            );
            vector::push_back(
                &mut open_orders_cmp,
                clob::test_construct_order(0, CLIENT_ID_ALICE,1 * FLOAT_SCALING, 10000, 10000, true, account_cap_user_alice)
            );
            assert!(open_orders == open_orders_cmp, 0);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap_alice);
        };
        end(test)
    }

    fun test_inject_and_match_taker_bid_with_quote_quantity_partial_lot_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        let owner = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test_with_tick_min(5000000, 2500000, 1 * FLOAT_SCALING, 10, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 100000;
            let alice_deposit_USDC: u64 = 100000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 5000, 5000, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 5000, 5000, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 10000, 10000, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 1 * FLOAT_SCALING, 100000, 100000, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let (base_quantity_filled, quote_quantity_filled) = clob::test_match_bid_with_quote_quantity(
                &mut pool,
                &account_cap,
                CLIENT_ID_BOB,
                45000,
                MAX_PRICE,
                0,
            );
            assert!(base_quantity_filled == 10000 + 4000, 0);
            assert!(quote_quantity_filled == 40200, 0);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        next_tx(&mut test, bob);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap_alice = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user_alice = account_owner(&account_cap_alice);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);

            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user_alice, 40200 - 100 - 100 + 50 + 50, 100000);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user_alice, 80000, 5000 + 1000);
            {
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_empty_tick_level(asks, 2 * FLOAT_SCALING);
            };
            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 5000, 1000, false, account_cap_user_alice)
                );
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(1, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 5000, 5000, false, account_cap_user_alice)
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 5 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 1 * FLOAT_SCALING, 100000, 100000, true, account_cap_user_alice)
                );
                let (_, _, bid, _) = get_pool_stat(&pool);
                clob::check_tick_level(bid, 1 * FLOAT_SCALING, &open_orders);
            };

            let open_orders = list_open_orders(&pool, &account_cap_alice);
            let mut open_orders_cmp = vector::empty<Order>();
            vector::push_back(
                &mut open_orders_cmp,
                clob::test_construct_order(0, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 5000, 1000, false, account_cap_user_alice)
            );
            vector::push_back(
                &mut open_orders_cmp,
                clob::test_construct_order(1, CLIENT_ID_ALICE, 5 * FLOAT_SCALING,5000, 5000, false, account_cap_user_alice)
            );
            vector::push_back(
                &mut open_orders_cmp,
                clob::test_construct_order(0, CLIENT_ID_ALICE, 1 * FLOAT_SCALING, 100000, 100000, true, account_cap_user_alice)
            );
            assert!(open_orders == open_orders_cmp, 0);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap_alice);
        };
        end(test)
    }

    // This scenario tests a user trying to place an order that's greater than lot_size but less than min_size.
    fun test_place_order_less_than_min_size_error_(mut test: Scenario): TransactionEffects {
        let (alice, _) = people();
        let owner: address = @0xF;
        let min_size = 100000000; // 0.1 SUI
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test_with_tick_min(0, 0, 1 * FLOAT_SCALING, min_size, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_sender<AccountCap>(&test);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            custodian::deposit(base_custodian, mint_for_testing<SUI>(10000000, ctx(&mut test)), account_cap_user);
            custodian::deposit(quote_custodian, mint_for_testing<USD>(10000000, ctx(&mut test)), account_cap_user);
            test::return_shared(pool);
            test::return_to_sender<AccountCap>(&test, account_cap);
        };

        // alice places limit orders
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let clock = test::take_shared<Clock>(&test);
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                5 * FLOAT_SCALING,
                10000000,
                CANCEL_OLDEST,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        end(test)
    }

    fun test_swap_exact_base_for_quote_min_size_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        let owner = @0xF;
        let min_size = 100000000; // 0.1 SUI
        let lot_size = 1000;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test_with_tick_min(0, 0, 1 * FLOAT_SCALING, min_size, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            // assuming 9 decimal points, alice gets 5 SUI and 5 USDC
            // alice places a limit buy of 0.2 SUI at $4, costing her 0.8 USDC
            // alice places a limit sell of 0.2 SUI at $5, costing her 0.2 SUI
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 50 * min_size;
            let alice_deposit_USDC: u64 = 50 * min_size;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 4 * FLOAT_SCALING, 2 * min_size, 2 * min_size, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 2 * min_size, 2 * min_size, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, bob);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap_alice = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user_alice = account_owner(&account_cap_alice);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);

            // alice has 4.2 USDC available and 0.8 USDC locked
            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user_alice, 4_200_000_000, 800_000_000);
            // alice has 4.8 SUI available and 0.2 SUI locked
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user_alice, 4_800_000_000, 200_000_000);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap_alice);
        };
        next_tx(&mut test, bob);
        {
            // bob pays 0.5001 USDC to buy as much SUI from the market as possible. He is matched against alice's $5 limit order.
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let (base_quantity_filled, quote_quantity_filled) = clob::test_match_bid_with_quote_quantity(
                &mut pool,
                &account_cap,
                CLIENT_ID_BOB,
                500_100_000,
                MAX_PRICE,
                0,
            );
            // bob's 0.5 USDC fills the minimum of 0.1 SUI and an additional 20 lots, 0.0002 at $5.
            assert!(base_quantity_filled == 1 * min_size + (20 * lot_size), 0);
            // all of bob's quote asset was filled.
            assert!(quote_quantity_filled == 500_100_000, 0);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        next_tx(&mut test, bob);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap_alice = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user_alice = account_owner(&account_cap_alice);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);

            // alice received bob's 0.5001 USDC, increasing the available balance to 4.7001 USDC
            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user_alice, 4_700_100_000, 800_000_000);
            // alice's locked SUI was reduced by 0.10002 SUI
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user_alice, 4_800_000_000, 99_980_000);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap_alice);
        };
        end(test)
    }

    fun test_inject_and_match_taker_bid_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        let owner = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(5000000, 2500000, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 10000;
            let alice_deposit_USDC: u64 = 10000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 1000, 1000, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 1 * FLOAT_SCALING, 10000, 10000, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user, 0, 10000);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user, 8000, 2000);
            let (next_bid_order_id, next_ask_order_id, _, _) = clob::get_pool_stat(&pool);
            assert!(next_bid_order_id == clob::order_id_for_test(1, true), 0);
            assert!(next_ask_order_id == clob::order_id_for_test(3, false), 0);
            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, false, account_cap_user)
                );
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(1, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, false, account_cap_user)
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 5 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(2, CLIENT_ID_ALICE,2 * FLOAT_SCALING, 1000, 1000, false, account_cap_user)
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 2 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE,1 * FLOAT_SCALING, 10000, 10000, true, account_cap_user)
                );
                let (_, _, bid, _) = get_pool_stat(&pool);
                clob::check_tick_level(bid, 1 * FLOAT_SCALING, &open_orders);
            };
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        // test match (bid side)
        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let (base_quantity_filled, quote_quantity_filled) = clob::test_match_bid(
                &mut pool,
                &account_cap,
                CLIENT_ID_BOB,
                1500,
                MAX_PRICE,
                0,
            );
            assert!(base_quantity_filled == 1500, 0);
            assert!(quote_quantity_filled == 4500 + 10 + 13, 0);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        next_tx(&mut test, bob);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap_alice = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user_alice = account_owner(&account_cap_alice);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);

            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user_alice, 4500 + 5 + 6, 10000);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user_alice, 8000, 500);
            {
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_empty_tick_level(asks, 2 * FLOAT_SCALING);
            };
            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(1, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, false, account_cap_user_alice)
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 5 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 1 * FLOAT_SCALING, 10000, 10000, true, account_cap_user_alice)
                );
                let (_, _, bid, _) = get_pool_stat(&pool);
                clob::check_tick_level(bid, 1 * FLOAT_SCALING, &open_orders);
            };
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap_alice);
        };
        end(test)
    }

    fun test_inject_and_match_taker_bid_with_maker_order_not_fully_filled_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        let owner = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(5000000, 2500000, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 10000;
            let alice_deposit_USDC: u64 = 10000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 1000, 1000, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 1 * FLOAT_SCALING, 10000, 10000, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user, 0, 10000);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user, 8000, 2000);
            let (next_bid_order_id, next_ask_order_id, _, _) = clob::get_pool_stat(&pool);
            assert!(next_bid_order_id == clob::order_id_for_test(1, true), 0);
            assert!(next_ask_order_id == clob::order_id_for_test(3, false), 0);
            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, false, account_cap_user)
                );
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(1, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, false, account_cap_user)
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 5 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(2, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 1000, 1000, false, account_cap_user)
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 2 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 1 * FLOAT_SCALING, 10000, 10000, true, account_cap_user)
                );
                let (_, _, bid, _) = get_pool_stat(&pool);
                clob::check_tick_level(bid, 1 * FLOAT_SCALING, &open_orders);
            };
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        // test match (bid side)
        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let (base_quantity_filled, quote_quantity_filled) = clob::test_match_bid(
                &mut pool,
                &account_cap,
                CLIENT_ID_BOB,
                1250,
                MAX_PRICE,
                0,
            );
            assert!(base_quantity_filled == 1250, 0);
            assert!(quote_quantity_filled == 3267, 0);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        next_tx(&mut test, bob);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap_alice = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user_alice = account_owner(&account_cap_alice);

            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user_alice, 8000, 750);
            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user_alice, 3258, 10000);

            {
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_empty_tick_level(asks, 2 * FLOAT_SCALING);
            };
            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 250, 250, false, account_cap_user_alice)
                );
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(1, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, false, account_cap_user_alice)
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 5 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 1 * FLOAT_SCALING, 10000, 10000, true, account_cap_user_alice)
                );
                let (_, _, bid, _) = get_pool_stat(&pool);
                clob::check_tick_level(bid, 1 * FLOAT_SCALING, &open_orders);
            };
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap_alice);
        };
        end(test)
    }

    fun test_inject_and_match_taker_ask_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        let owner = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(5000000, 2500000, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 10000;
            let alice_deposit_USDC: u64 = 10000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        // test inject limit order and match (ask side)
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 1000, 1000, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 10 * FLOAT_SCALING, 10000, 10000, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user, 3000, 7000);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user, 0, 10000);
            let (next_bid_order_id, next_ask_order_id, _, _) = clob::get_pool_stat(&pool);
            assert!(next_bid_order_id == clob::order_id_for_test(3, true), 0);
            assert!(next_ask_order_id == clob::order_id_for_test(1, false), 0);

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, true, account_cap_user)
                );
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(1, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, true, account_cap_user)
                );
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_tick_level(bids, 5 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(2, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 1000, 1000, true, account_cap_user)
                );
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_tick_level(bids, 2 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 10 * FLOAT_SCALING, 10000, 10000, false, account_cap_user)
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 10 * FLOAT_SCALING, &open_orders);
            };
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        // test match (ask side)
        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let (base_quantity_filled, quote_quantity_filled) = clob::test_match_ask(
                &mut pool,
                &account_cap,
                CLIENT_ID_BOB,
                1500,
                MIN_PRICE,
                0,
            );
            assert!(base_quantity_filled == 1500, 0);
            assert!(quote_quantity_filled == 6000 - 13 - 13 - 5, 0);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        next_tx(&mut test, bob);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            custodian::assert_user_balance<USD>(
                quote_custodian,
                account_cap_user,
                3000 + 6 + 6 + 2,
                7000 - 2500 - 2500 - 1000
            );
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user, 1500, 10000);
            {
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_empty_tick_level(bids, 5 * FLOAT_SCALING);
            };
            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(2, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 500, 500, true, account_cap_user)
                );
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_tick_level(bids, 2 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 10 * FLOAT_SCALING, 10000, 10000, false, account_cap_user)
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 10 * FLOAT_SCALING, &open_orders);
            };
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        end(test)
    }

    fun test_inject_and_match_taker_bid_with_quote_quantity_and_expiration_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        let owner = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(5000000, 2500000, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        // test inject limit order and match (bid side)
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 100000;
            let alice_deposit_USDC: u64 = 100000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            clob::test_inject_limit_order_with_expiration(
                &mut pool,
                CLIENT_ID_ALICE,
                5 * FLOAT_SCALING,
                5000,
                5000,
                false,
                CANCEL_OLDEST,
                TIMESTAMP_INF,
                &account_cap,
                ctx(&mut test)
            );
            clob::test_inject_limit_order_with_expiration(
                &mut pool,
                CLIENT_ID_ALICE,
                2 * FLOAT_SCALING,
                5000,
                5000,
                false,
                CANCEL_OLDEST,
                0,
                &account_cap,
                ctx(&mut test)
            );
            clob::test_inject_limit_order_with_expiration(
                &mut pool,
                CLIENT_ID_ALICE,
                2 * FLOAT_SCALING,
                10000,
                10000,
                false,
                CANCEL_OLDEST,
                TIMESTAMP_INF,
                &account_cap,
                ctx(&mut test)
            );
            clob::test_inject_limit_order_with_expiration(
                &mut pool,
                CLIENT_ID_ALICE,
                1 * FLOAT_SCALING,
                100000,
                100000,
                true,
                CANCEL_OLDEST,
                0,
                &account_cap,
                ctx(&mut test)
            );
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);

            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user, 0, 100000);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user, 80000, 20000);
            let (next_bid_order_id, next_ask_order_id, _, _) = clob::get_pool_stat(&pool);
            assert!(next_bid_order_id == clob::order_id_for_test(1, true), 0);
            assert!(next_ask_order_id == clob::order_id_for_test(3, false), 0);

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order_with_expiration(
                        0,
                        CLIENT_ID_ALICE,
                        5 * FLOAT_SCALING,
                        5000,
                        5000,
                        false,
                        account_cap_user,
                        TIMESTAMP_INF
                    )
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 5 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order_with_expiration(1, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 5000, 5000, false, account_cap_user, 0)
                );
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order_with_expiration(
                        2,
                        CLIENT_ID_ALICE,
                        2 * FLOAT_SCALING,
                        10000,
                        10000,
                        false,
                        account_cap_user,
                        TIMESTAMP_INF
                    )
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 2 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 1 * FLOAT_SCALING, 100000, 100000, true, account_cap_user)
                );
                let (_, _, bid, _) = get_pool_stat(&pool);
                clob::check_tick_level(bid, 1 * FLOAT_SCALING, &open_orders);
            };
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        // test match (bid side)
        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let (base_quantity_filled, quote_quantity_filled) = clob::test_match_bid_with_quote_quantity(
                &mut pool,
                &account_cap,
                CLIENT_ID_BOB,
                45000,
                MAX_PRICE,
                1,
            );
            assert!(base_quantity_filled == 10000 + 4000, 0);
            assert!(quote_quantity_filled == 40200, 0);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        next_tx(&mut test, bob);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            // rebate fee in base asset 3
            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user, 40200 - 100 - 100 + 50 + 50, 100000);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user, 85000, 1000);
            {
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_empty_tick_level(asks, 2 * FLOAT_SCALING);
            };
            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 5000, 1000, false, account_cap_user)
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 5 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 1 * FLOAT_SCALING, 100000, 100000, true, account_cap_user)
                );
                let (_, _, bid, _) = get_pool_stat(&pool);
                clob::check_tick_level(bid, 1 * FLOAT_SCALING, &open_orders);
            };
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        end(test)
    }

    fun test_inject_and_match_taker_bid_with_expiration_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        let owner = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(5000000, 2500000, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        // test inject limit order and match (bid side)
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 10000;
            let alice_deposit_USDC: u64 = 10000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            clob::test_inject_limit_order_with_expiration(
                &mut pool,
                CLIENT_ID_ALICE,
                5 * FLOAT_SCALING,
                500,
                500,
                false,
                CANCEL_OLDEST,
                TIMESTAMP_INF,
                &account_cap,
                ctx(&mut test)
            );
            clob::test_inject_limit_order_with_expiration(
                &mut pool,
                CLIENT_ID_ALICE,
                2 * FLOAT_SCALING,
                500,
                500,
                false,
                CANCEL_OLDEST,
                0,
                &account_cap,
                ctx(&mut test)
            );
            clob::test_inject_limit_order_with_expiration(
                &mut pool,
                CLIENT_ID_ALICE,
                2 * FLOAT_SCALING,
                1000,
                1000,
                false,
                CANCEL_OLDEST,
                TIMESTAMP_INF,
                &account_cap,
                ctx(&mut test)
            );
            clob::test_inject_limit_order_with_expiration(
                &mut pool,
                CLIENT_ID_ALICE,
                1 * FLOAT_SCALING,
                10000,
                10000,
                true,
                CANCEL_OLDEST,
                0,
                &account_cap,
                ctx(&mut test)
            );
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let clock = test::take_shared<Clock>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);

            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user, 0, 10000);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user, 8000, 2000);
            let (next_bid_order_id, next_ask_order_id, _, _) = clob::get_pool_stat(&pool);
            assert!(next_bid_order_id == clob::order_id_for_test(1, true), 0);
            assert!(next_ask_order_id == clob::order_id_for_test(3, false), 0);
            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order_with_expiration(
                        0,
                        CLIENT_ID_ALICE,
                        5 * FLOAT_SCALING,
                        500,
                        500,
                        false,
                        account_cap_user,
                        TIMESTAMP_INF
                    )
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 5 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order_with_expiration(1, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 500, 500, false, account_cap_user, 0)
                );
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order_with_expiration(
                        2,
                        CLIENT_ID_ALICE,
                        2 * FLOAT_SCALING,
                        1000,
                        1000,
                        false,
                        account_cap_user,
                        TIMESTAMP_INF
                    )
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 2 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 1 * FLOAT_SCALING, 10000, 10000, true, account_cap_user)
                );
                let (_, _, bid, _) = get_pool_stat(&pool);
                clob::check_tick_level(bid, 1 * FLOAT_SCALING, &open_orders);
            };
            test::return_shared(clock);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        // test match (bid side)
        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let (base_quantity_filled, quote_quantity_filled) = clob::test_match_bid(
                &mut pool,
                &account_cap,
                CLIENT_ID_BOB,
                1500,
                MAX_PRICE,
                1,
            );
            assert!(base_quantity_filled == 1500, 0);
            assert!(quote_quantity_filled == 4500 + 10 + 13, 0);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        next_tx(&mut test, bob);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            // rebate fee in base asset 3
            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user, 4500 + 5 + 6, 10000);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user, 8500, 0);
            {
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_empty_tick_level(asks, 2 * FLOAT_SCALING);
            };
            {
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_empty_tick_level(asks, 5 * FLOAT_SCALING);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 1 * FLOAT_SCALING, 10000, 10000, true, account_cap_user)
                );
                let (_, _, bid, _) = get_pool_stat(&pool);
                clob::check_tick_level(bid, 1 * FLOAT_SCALING, &open_orders);
            };
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        end(test)
    }

    fun test_inject_and_match_taker_ask_with_expiration_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        let owner = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(5000000, 2500000, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 10000;
            let alice_deposit_USDC: u64 = 10000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        // test inject limit order and match (ask side)
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            clob::test_inject_limit_order_with_expiration(
                &mut pool,
                CLIENT_ID_ALICE,
                5 * FLOAT_SCALING,
                500,
                500,
                true,
                CANCEL_OLDEST,
                TIMESTAMP_INF,
                &account_cap,
                ctx(&mut test)
            );
            clob::test_inject_limit_order_with_expiration(
                &mut pool,
                CLIENT_ID_ALICE,
                5 * FLOAT_SCALING,
                1000,
                1000,
                true,
                CANCEL_OLDEST,
                0,
                &account_cap,
                ctx(&mut test)
            );
            clob::test_inject_limit_order_with_expiration(
                &mut pool,
                CLIENT_ID_ALICE,
                2 * FLOAT_SCALING,
                1000,
                1000,
                true,
                CANCEL_OLDEST,
                TIMESTAMP_INF,
                &account_cap,
                ctx(&mut test)
            );
            clob::test_inject_limit_order_with_expiration(
                &mut pool,
                CLIENT_ID_ALICE,
                10 * FLOAT_SCALING,
                10000,
                10000,
                false,
                CANCEL_OLDEST,
                TIMESTAMP_INF,
                &account_cap,
                ctx(&mut test)
            );
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user, 500, 9500);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user, 0, 10000);
            let (next_bid_order_id, next_ask_order_id, _, _) = clob::get_pool_stat(&pool);
            assert!(next_bid_order_id == clob::order_id_for_test(3, true), 0);
            assert!(next_ask_order_id == clob::order_id_for_test(1, false), 0);

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order_with_expiration(
                        0,
                        CLIENT_ID_ALICE,
                        5 * FLOAT_SCALING,
                        500,
                        500,
                        true,
                        account_cap_user,
                        TIMESTAMP_INF
                    )
                );
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order_with_expiration(
                        1,
                        CLIENT_ID_ALICE,
                        5 * FLOAT_SCALING,
                        1000,
                        1000,
                        true,
                        account_cap_user,
                        0,
                    )
                );
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_tick_level(bids, 5 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order_with_expiration(
                        2,
                        CLIENT_ID_ALICE,
                        2 * FLOAT_SCALING,
                        1000,
                        1000,
                        true,
                        account_cap_user,
                        TIMESTAMP_INF
                    )
                );
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_tick_level(bids, 2 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order_with_expiration(
                        0,
                        CLIENT_ID_ALICE,
                        10 * FLOAT_SCALING,
                        10000,
                        10000,
                        false,
                        account_cap_user,
                        TIMESTAMP_INF
                    )
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 10 * FLOAT_SCALING, &open_orders);
            };
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        // test match (ask side)
        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let (base_quantity_filled, quote_quantity_filled) = clob::test_match_ask(
                &mut pool,
                &account_cap,
                CLIENT_ID_BOB,
                1500,
                MIN_PRICE,
                1,
            );
            assert!(base_quantity_filled == 1500, 0);
            assert!(quote_quantity_filled == 4500 - 13 - 10, 0);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        next_tx(&mut test, bob);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            custodian::assert_user_balance<USD>(
                quote_custodian,
                account_cap_user,
                5500 + 6 + 5,
                9500 - 2500 - 5000 - 2000
            );
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user, 1500, 10000);
            {
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_empty_tick_level(bids, 5 * FLOAT_SCALING);
            };
            {
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_empty_tick_level(bids, 2 * FLOAT_SCALING);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 10 * FLOAT_SCALING, 10000, 10000, false, account_cap_user)
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 10 * FLOAT_SCALING, &open_orders);
            };
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        end(test)
    }

    fun test_inject_and_price_limit_affected_match_taker_bid_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        let owner = @0xFF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(0, 0, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 100;
            let alice_deposit_USDC: u64 = 10;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 2, 2, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 3, 3, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 10, 10, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 1 * FLOAT_SCALING, 10, 10, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user, 0, 10);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user, 85, 15);
            let (next_bid_order_id, next_ask_order_id, _, _) = clob::get_pool_stat(&pool);
            assert!(next_bid_order_id == clob::order_id_for_test(1, true), 0);
            assert!(next_ask_order_id == clob::order_id_for_test(3, false), 0);

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 2, 2, false, account_cap_user)
                );
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(1, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 3, 3, false, account_cap_user)
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 5 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(2, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 10, 10, false, account_cap_user)
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 2 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 1 * FLOAT_SCALING, 10, 10, true, account_cap_user)
                );
                let (_, _, bid, _) = get_pool_stat(&pool);
                clob::check_tick_level(bid, 1 * FLOAT_SCALING, &open_orders);
            };
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        // test match with price limit (bid side)
        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let (base_quantity_filled, quote_quantity_filled) = clob::test_match_bid(
                &mut pool,
                &account_cap,
                CLIENT_ID_BOB,
                20,
                5 * FLOAT_SCALING,
                0
            );
            assert!(base_quantity_filled == 15, 0);
            assert!(quote_quantity_filled == 45, 0);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        next_tx(&mut test, bob);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user, 45, 10);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user, 85, 0);
            {
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_empty_tick_level(asks, 2 * FLOAT_SCALING);
            };
            {
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_empty_tick_level(asks, 5 * FLOAT_SCALING);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 1 * FLOAT_SCALING, 10, 10, true, account_cap_user)
                );
                let (_, _, bid, _) = get_pool_stat(&pool);
                clob::check_tick_level(bid, 1 * FLOAT_SCALING, &open_orders);
            };
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        end(test)
    }

    fun test_inject_and_price_limit_affected_match_taker_ask_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        let owner = @0xFF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(0, 0, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 10;
            let alice_deposit_USDC: u64 = 100;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        // test inject limit order and match (ask side)
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            // let account_cap_user = get_account_cap_user(&account_cap);
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 2, 2, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 3, 3, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 10, 10, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 20 * FLOAT_SCALING, 10, 10, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user, 55, 45);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user, 0, 10);
            let (next_bid_order_id, next_ask_order_id, _, _) = clob::get_pool_stat(&pool);
            assert!(next_bid_order_id == clob::order_id_for_test(3, true), 0);
            assert!(next_ask_order_id == clob::order_id_for_test(1, false), 0);

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 2, 2, true, account_cap_user)
                );
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(1, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 3, 3, true, account_cap_user)
                );
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_tick_level(bids, 5 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(2, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 10, 10, true, account_cap_user)
                );
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_tick_level(bids, 2 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 20 * FLOAT_SCALING, 10, 10, false, account_cap_user)
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 20 * FLOAT_SCALING, &open_orders);
            };
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        // test match with price limit (ask side)
        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let (base_quantity_filled, quote_quantity_filled) = clob::test_match_ask(
                &mut pool,
                &account_cap,
                CLIENT_ID_BOB,
                10,
                3 * FLOAT_SCALING,
                0,
            );
            assert!(base_quantity_filled == 5, 0);
            assert!(quote_quantity_filled == 25, 0);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        next_tx(&mut test, bob);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user, 55, 20);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user, 5, 10);
            {
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_empty_tick_level(bids, 5 * FLOAT_SCALING);
            };
            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(2, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 10, 10, true, account_cap_user)
                );
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_tick_level(bids, 2 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 20 * FLOAT_SCALING, 10, 10, false, account_cap_user)
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 20 * FLOAT_SCALING, &open_orders);
            };
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        end(test)
    }

    fun test_inject_and_price_limit_affected_match_taker_ask_returned_pool_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        let owner = @0xFF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test_wrapped_pool(0, 0, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut wrapped_pool = test::take_shared<WrappedPool<SUI, USD>>(&test);
            let pool = borrow_mut_pool<SUI, USD>(&mut wrapped_pool);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(pool);
            let alice_deposit_WSUI: u64 = 10;
            let alice_deposit_USDC: u64 = 100;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            test::return_shared(wrapped_pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        // test inject limit order and match (ask side)
        next_tx(&mut test, alice);
        {
            let mut wrapped_pool = test::take_shared<WrappedPool<SUI, USD>>(&test);
            let pool = borrow_mut_pool<SUI, USD>(&mut wrapped_pool);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            // let account_cap_user = get_account_cap_user(&account_cap);
            clob::test_inject_limit_order(
                pool,
                CLIENT_ID_ALICE,
                5 * FLOAT_SCALING,
                2,
                2,
                true,
                CANCEL_OLDEST,
                &account_cap,
                ctx(&mut test)
            );
            clob::test_inject_limit_order(
                pool,
                CLIENT_ID_ALICE,
                5 * FLOAT_SCALING,
                3,
                3,
                true,
                CANCEL_OLDEST,
                &account_cap,
                ctx(&mut test)
            );
            clob::test_inject_limit_order(
                pool,
                CLIENT_ID_ALICE,
                2 * FLOAT_SCALING,
                10,
                10,
                true,
                CANCEL_OLDEST,
                &account_cap,
                ctx(&mut test)
            );
            clob::test_inject_limit_order(
                pool,
                CLIENT_ID_ALICE,
                20 * FLOAT_SCALING,
                10,
                10,
                false,
                CANCEL_OLDEST,
                &account_cap,
                ctx(&mut test)
            );
            test::return_shared(wrapped_pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, alice);
        {
            let mut wrapped_pool = test::take_shared<WrappedPool<SUI, USD>>(&test);
            let pool = borrow_mut_pool<SUI, USD>(&mut wrapped_pool);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(pool);
            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user, 55, 45);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user, 0, 10);
            let (next_bid_order_id, next_ask_order_id, _, _) = clob::get_pool_stat(pool);
            assert!(next_bid_order_id == clob::order_id_for_test(3, true), 0);
            assert!(next_ask_order_id == clob::order_id_for_test(1, false), 0);

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 2, 2, true, account_cap_user)
                );
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(1, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 3, 3, true, account_cap_user)
                );
                let (_, _, bids, _) = get_pool_stat(pool);
                clob::check_tick_level(bids, 5 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(2, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 10, 10, true, account_cap_user)
                );
                let (_, _, bids, _) = get_pool_stat(pool);
                clob::check_tick_level(bids, 2 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 20 * FLOAT_SCALING, 10, 10, false, account_cap_user)
                );
                let (_, _, _, asks) = get_pool_stat(pool);
                clob::check_tick_level(asks, 20 * FLOAT_SCALING, &open_orders);
            };
            test::return_shared(wrapped_pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        // test match with price limit (ask side)
        next_tx(&mut test, bob);
        {
            let mut wrapped_pool = test::take_shared<WrappedPool<SUI, USD>>(&test);
            let pool = borrow_mut_pool<SUI, USD>(&mut wrapped_pool);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let (base_quantity_filled, quote_quantity_filled) = clob::test_match_ask(
                pool,
                &account_cap,
                CLIENT_ID_BOB,
                10,
                3 * FLOAT_SCALING,
                0,
            );
            assert!(base_quantity_filled == 5, 0);
            assert!(quote_quantity_filled == 25, 0);
            test::return_shared(wrapped_pool);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        next_tx(&mut test, bob);
        {
            let mut wrapped_pool = test::take_shared<WrappedPool<SUI, USD>>(&test);
            let pool = borrow_mut_pool<SUI, USD>(&mut wrapped_pool);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(pool);
            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user, 55, 20);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user, 5, 10);
            {
                let (_, _, bids, _) = get_pool_stat(pool);
                clob::check_empty_tick_level(bids, 5 * FLOAT_SCALING);
            };
            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(2, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 10, 10, true, account_cap_user)
                );
                let (_, _, bids, _) = get_pool_stat(pool);
                clob::check_tick_level(bids, 2 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 20 * FLOAT_SCALING, 10, 10, false, account_cap_user)
                );
                let (_, _, _, asks) = get_pool_stat(pool);
                clob::check_tick_level(asks, 20 * FLOAT_SCALING, &open_orders);
            };
            test::return_shared(wrapped_pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        end(test)
    }

    fun test_remove_order_(mut test: Scenario): TransactionEffects {
        let (alice, _) = people();
        let owner: address = @0xF;
        next_tx(&mut test, owner);
        {
            clob::setup_test(0, 0, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 10;
            let alice_deposit_USDC: u64 = 100;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);

            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 2, 2, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 3, 3, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 10, 10, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 10, 10, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 20 * FLOAT_SCALING, 10, 10, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 2, 2, true, account_cap_user)
                );
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(1, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 3, 3, true, account_cap_user)
                );
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_tick_level(bids, 5 * FLOAT_SCALING, &open_orders);
            };
            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(2, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 10, 10, true, account_cap_user)
                );
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(3, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 10, 10, true, account_cap_user)
                );
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_tick_level(bids, 2 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 20 * FLOAT_SCALING, 10, 10, false, account_cap_user)
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 20 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 2, 2, true, account_cap_user)
                );
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(1, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 2, 3, true, account_cap_user)
                );
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_tick_level(bids, 5 * FLOAT_SCALING, &open_orders);
            };

            // check usr open orders before cancel
            {
                let mut usr_open_orders_cmp = vector::empty<u64>();
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(0, true));
                vector::push_back(&mut usr_open_orders_cmp, 5 * FLOAT_SCALING);
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(1, true));
                vector::push_back(&mut usr_open_orders_cmp, 5 * FLOAT_SCALING);
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(2, true));
                vector::push_back(&mut usr_open_orders_cmp, 2 * FLOAT_SCALING);
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(3, true));
                vector::push_back(&mut usr_open_orders_cmp, 2 * FLOAT_SCALING);
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(0, false));
                vector::push_back(&mut usr_open_orders_cmp, 20 * FLOAT_SCALING);
                clob::check_usr_open_orders(clob::get_usr_open_orders(&pool, account_cap_user), &usr_open_orders_cmp);
                let user_open_orders = clob::get_usr_open_orders(&pool, account_cap_user);
                clob::check_usr_open_orders(user_open_orders, &usr_open_orders_cmp);
            };

            clob::test_remove_order(&mut pool, 0, 0, true, account_cap_user);
            {
                // check tick level from pool after remove order
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(1, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 3, 3, true, account_cap_user)
                );
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_tick_level(bids, 5 * FLOAT_SCALING, &open_orders);
                // check usr open orders after remove order
                let mut usr_open_orders_cmp = vector::empty<u64>();
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(0, false));
                vector::push_back(&mut usr_open_orders_cmp, 20 * FLOAT_SCALING);
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(1, true));
                vector::push_back(&mut usr_open_orders_cmp, 5 * FLOAT_SCALING);
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(2, true));
                vector::push_back(&mut usr_open_orders_cmp, 2 * FLOAT_SCALING);
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(3, true));
                vector::push_back(&mut usr_open_orders_cmp, 2 * FLOAT_SCALING);
                let user_open_orders = clob::get_usr_open_orders(&pool, account_cap_user);
                clob::check_usr_open_orders(user_open_orders, &usr_open_orders_cmp);
            };

            clob::test_remove_order(&mut pool, 0, 1, true, account_cap_user);
            {
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_empty_tick_level(bids, 5 * FLOAT_SCALING);
                let mut usr_open_orders_cmp = vector::empty<u64>();
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(0, false));
                vector::push_back(&mut usr_open_orders_cmp, 20 * FLOAT_SCALING);
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(3, true));
                vector::push_back(&mut usr_open_orders_cmp, 2 * FLOAT_SCALING);
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(2, true));
                vector::push_back(&mut usr_open_orders_cmp, 2 * FLOAT_SCALING);
                clob::check_usr_open_orders(
                    clob::get_usr_open_orders(&pool, account_cap_user),
                    &usr_open_orders_cmp
                );
            };

            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        end(test)
    }

    fun test_remove_all_orders_(mut test: Scenario): TransactionEffects {
        let (alice, _) = people();
        let owner: address = @0xF;
        next_tx(&mut test, owner);
        {
            clob::setup_test(0, 0, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 10;
            let alice_deposit_USDC: u64 = 100;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);

            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 2, 2, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 3, 3, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 10, 10, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 10, 10, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 20 * FLOAT_SCALING, 10, 10, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 2, 2, true, account_cap_user)
                );
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(1, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 3, 3, true, account_cap_user)
                );
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_tick_level(bids, 5 * FLOAT_SCALING, &open_orders);
            };
            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(2, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 10, 10, true, account_cap_user)
                );
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(3, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 10, 10, true, account_cap_user)
                );
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_tick_level(bids, 2 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 20 * FLOAT_SCALING, 10, 10, false, account_cap_user)
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 20 * FLOAT_SCALING, &open_orders);
            };

            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 2, 2, true, account_cap_user)
                );
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(1, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 3, 3, true, account_cap_user)
                );
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_tick_level(bids, 5 * FLOAT_SCALING, &open_orders);
            };

            // check usr open orders before cancel
            {
                let mut usr_open_orders_cmp = vector::empty<u64>();
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(0, true));
                vector::push_back(&mut usr_open_orders_cmp, 5 * FLOAT_SCALING);
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(1, true));
                vector::push_back(&mut usr_open_orders_cmp, 5 * FLOAT_SCALING);
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(2, true));
                vector::push_back(&mut usr_open_orders_cmp, 2 * FLOAT_SCALING);
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(3, true));
                vector::push_back(&mut usr_open_orders_cmp, 2 * FLOAT_SCALING);
                vector::push_back(&mut usr_open_orders_cmp, order_id_for_test(0, false));
                vector::push_back(&mut usr_open_orders_cmp, 20 * FLOAT_SCALING);
                clob::check_usr_open_orders(clob::get_usr_open_orders(&pool, account_cap_user), &usr_open_orders_cmp);
                let user_open_orders = clob::get_usr_open_orders(&pool, account_cap_user);
                clob::check_usr_open_orders(user_open_orders, &usr_open_orders_cmp);
            };

            clob::cancel_all_orders(&mut pool, &account_cap);
            {
                let usr_open_orders_cmp = vector::empty<u64>();
                let user_open_orders = clob::get_usr_open_orders(&pool, account_cap_user);
                clob::check_usr_open_orders(user_open_orders, &usr_open_orders_cmp);

                // check tick level after remove
                let (_, _, bids, asks) = get_pool_stat(&pool);
                clob::check_empty_tick_level(bids, 5 * FLOAT_SCALING);
                clob::check_empty_tick_level(bids, 2 * FLOAT_SCALING);
                clob::check_empty_tick_level(asks, 20 * FLOAT_SCALING);
                let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
                custodian::assert_user_balance(base_custodian, account_cap_user, 10, 0);
                custodian::assert_user_balance(quote_custodian, account_cap_user, 100, 0);
                let (base_avail, base_locked, quote_avail, quote_locked) = account_balance(&pool, &account_cap);
                assert!(base_avail == 10, 0);
                assert!(base_locked == 0, 0);
                assert!(quote_avail == 100, 0);
                assert!(quote_locked == 0, 0);
            };
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        end(test)
    }

    // This test covers the following scenario:
    // In an order book, there are only some limit buy orders placed by Alice.
    // When Alice uses a market sell order to consume liquidity from the order book
    // and matches her own limit buy orders,
    // we needs to cancel all the previous limit buy orders
    // and correctly refunding to her custodian account
    fun test_place_market_sell_order_with_skipping_self_matching_(mut test: Scenario): TransactionEffects {
        let (alice, _) = people();
        let owner: address = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(5000000, 2500000, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_sender<AccountCap>(&test);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            custodian::deposit(base_custodian, mint_for_testing<SUI>(10000, ctx(&mut test)), account_cap_user);
            custodian::deposit(quote_custodian, mint_for_testing<USD>(100000, ctx(&mut test)), account_cap_user);
            test::return_shared(pool);
            test::return_to_sender<AccountCap>(&test, account_cap);
        };

        // alice places limit orders
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let clock = test::take_shared<Clock>(&test);
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                5 * FLOAT_SCALING,
                2000,
                CANCEL_OLDEST,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                5 * FLOAT_SCALING,
                3000,
                CANCEL_OLDEST,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                2 * FLOAT_SCALING,
                10000,
                CANCEL_OLDEST,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                20 * FLOAT_SCALING,
                10000,
                CANCEL_OLDEST,
                false,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            let (next_bid_order_id, next_ask_order_id, _, _) = clob::get_pool_stat(&pool);
            assert!(next_bid_order_id == clob::order_id_for_test(3, true), 0);
            assert!(next_ask_order_id == clob::order_id_for_test(1, false), 0);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            custodian::assert_user_balance(base_custodian, account_cap_user, 0, 10000);
            custodian::assert_user_balance(quote_custodian, account_cap_user, 55000, 45000);
            let (base_avail, base_locked, quote_avail, quote_locked) = account_balance(&pool, &account_cap);
            assert!(base_avail == 0, 0);
            assert!(base_locked == 10000, 0);
            assert!(quote_avail == 55000, 0);
            assert!(quote_locked == 45000, 0);
            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        // alice places market order
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let clock = test::take_shared<Clock>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let (coin1, coin2) =clob::place_market_order<SUI, USD>(&mut pool, &account_cap, CLIENT_ID_ALICE, 6000,
                false,
                mint_for_testing<SUI>(6000, ctx(&mut test)),
                mint_for_testing<USD>(0, ctx(&mut test)),
                &clock,
                ctx(&mut test));
            assert!(coin::value<SUI>(&coin1) == 6000, 0);
            assert!(coin::value<USD>(&coin2) == 0, 0);
            burn_for_testing(coin1);
            burn_for_testing(coin2);

            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            custodian::assert_user_balance(base_custodian, account_cap_user, 0, 10000);
            custodian::assert_user_balance(quote_custodian, account_cap_user, 100000, 0);
            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        end(test)
    }

    // This test covers the following scenario:
    // In an order book, there are only some limit sell orders placed by Alice.
    // When Alice uses a market buy order to consume liquidity from the order book
    // and matches her own limit sell orders,
    // we needs to cancel all the previous limit sell orders
    // and correctly refunding to her custodian account
    fun test_place_market_buy_order_with_skipping_self_matching_(mut test: Scenario): TransactionEffects {
        let (alice, _) = people();
        let owner: address = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(5000000, 2500000, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_sender<AccountCap>(&test);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            custodian::deposit(base_custodian, mint_for_testing<SUI>(15000, ctx(&mut test)), account_cap_user);
            custodian::deposit(quote_custodian, mint_for_testing<USD>(100000, ctx(&mut test)), account_cap_user);
            test::return_shared(pool);
            test::return_to_sender<AccountCap>(&test, account_cap);
        };

        // alice places limit orders
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let clock = test::take_shared<Clock>(&test);
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                5 * FLOAT_SCALING,
                2000,
                CANCEL_OLDEST,
                false,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                5 * FLOAT_SCALING,
                3000,
                CANCEL_OLDEST,
                false,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                2 * FLOAT_SCALING,
                10000,
                CANCEL_OLDEST,
                false,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                1 * FLOAT_SCALING,
                10000,
                CANCEL_OLDEST,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            let (next_bid_order_id, next_ask_order_id, _, _) = clob::get_pool_stat(&pool);
            assert!(next_bid_order_id == clob::order_id_for_test(1, true), 0);
            assert!(next_ask_order_id == clob::order_id_for_test(3, false), 0);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            custodian::assert_user_balance(base_custodian, account_cap_user, 0, 15000);
            custodian::assert_user_balance(quote_custodian, account_cap_user, 90000, 10000);
            let (base_avail, base_locked, quote_avail, quote_locked) = account_balance(&pool, &account_cap);
            assert!(base_avail == 0, 0);
            assert!(base_locked == 15000, 0);
            assert!(quote_avail == 90000, 0);
            assert!(quote_locked == 10000, 0);
            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        // alice places market buy order
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let clock = test::take_shared<Clock>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let (coin1, coin2) =clob::place_market_order<SUI, USD>(&mut pool, &account_cap, CLIENT_ID_ALICE, 1000,
                true,
                mint_for_testing<SUI>(0, ctx(&mut test)),
                mint_for_testing<USD>(1000, ctx(&mut test)),
                &clock,
                ctx(&mut test));
            assert!(coin::value<SUI>(&coin1) == 0, 0);
            assert!(coin::value<USD>(&coin2) == 1000, 0);
            burn_for_testing(coin1);
            burn_for_testing(coin2);

            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            custodian::assert_user_balance(base_custodian, account_cap_user, 15000, 0);
            custodian::assert_user_balance(quote_custodian, account_cap_user, 90000, 10000);
            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        end(test)
    }

    // This test covers the following scenario:
    // there are some limit buy orders placed by Alice.
    // When Alice continue to place a limit sell order
    // and it can be matched with her own previous limit buy order
    // We need to cancel all limit buy orders within the range of matching with the limit sell order.
    // and correctly refunding to her custodian account
    fun test_place_limit_order_with_skipping_self_matching_(mut test: Scenario): TransactionEffects {
        let (alice, _) = people();
        let owner: address = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(5000000, 2500000, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_sender<AccountCap>(&test);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            custodian::deposit(base_custodian, mint_for_testing<SUI>(10000, ctx(&mut test)), account_cap_user);
            custodian::deposit(quote_custodian, mint_for_testing<USD>(100000, ctx(&mut test)), account_cap_user);
            test::return_shared(pool);
            test::return_to_sender<AccountCap>(&test, account_cap);
        };
        // alice places limit orders
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let clock = test::take_shared<Clock>(&test);
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                5 * FLOAT_SCALING,
                2000,
                CANCEL_OLDEST,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                5 * FLOAT_SCALING,
                3000,
                CANCEL_OLDEST,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                2 * FLOAT_SCALING,
                10000,
                CANCEL_OLDEST,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                20 * FLOAT_SCALING,
                10000,
                CANCEL_OLDEST,
                false,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            let (next_bid_order_id, next_ask_order_id, _, _) = clob::get_pool_stat(&pool);
            assert!(next_bid_order_id == clob::order_id_for_test(3, true), 0);
            assert!(next_ask_order_id == clob::order_id_for_test(1, false), 0);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            custodian::assert_user_balance(base_custodian, account_cap_user, 0, 10000);
            custodian::assert_user_balance(quote_custodian, account_cap_user, 55000, 45000);
            let (base_avail, base_locked, quote_avail, quote_locked) = account_balance(&pool, &account_cap);
            assert!(base_avail == 0, 0);
            assert!(base_locked == 10000, 0);
            assert!(quote_avail == 55000, 0);
            assert!(quote_locked == 45000, 0);
            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_sender<AccountCap>(&test);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, _) = clob::borrow_mut_custodian(&mut pool);
            custodian::deposit(base_custodian, mint_for_testing<SUI>(4000, ctx(&mut test)), account_cap_user);
            test::return_shared(pool);
            test::return_to_sender<AccountCap>(&test, account_cap);
        };
        // alice places limit order
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_sender<AccountCap>(&test);
            let clock = test::take_shared<Clock>(&test);
            let (base_quantity_filled, quote_quantity_filled, is_placed, order_id) = clob::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                4 * FLOAT_SCALING,
                4000,
                CANCEL_OLDEST,
                false,
                TIMESTAMP_INF,
                POST_OR_ABORT,
                &clock,
                &account_cap,
                ctx(&mut test)
            );
            assert!(base_quantity_filled == 0, 0);
            assert!(quote_quantity_filled == 0, 0);
            assert!(is_placed == true, 0);
            assert!(order_id == MIN_ASK_ORDER_ID + 1, 0);

            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        // check alice's balance
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_sender<AccountCap>(&test);
            let clock = test::take_shared<Clock>(&test);

            let  (base_avail, base_locked, quote_avail, quote_locked) = account_balance<SUI, USD>(&pool, &account_cap);
            assert!(base_avail == 0, 0);
            assert!(base_locked == 10000 + 4000, 0);
            assert!(quote_avail == 80000, 0);
            assert!(quote_locked == 20000, 0);

            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        end(test)
    }

    // This test scenario is similar to "test_place_market_order_with_skipping_self_matching_",
    // but it verifies the logic when we want to swap the exact quote asset for the base asset.
    fun test_swap_exact_quote_for_base_with_skipping_self_matching_(mut test: Scenario): TransactionEffects {
        let (alice, _) = people();
        let owner = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(5000000, 2500000, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 100000;
            let alice_deposit_USDC: u64 = 100000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 5000, 5000, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 5000, 5000, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 10000, 10000, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE,1 * FLOAT_SCALING, 100000, 100000, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let clock = test::take_shared<Clock>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let (base_coin, quote_coin, _) = clob::swap_exact_quote_for_base(
                &mut pool,
                CLIENT_ID_ALICE,
                &account_cap,
                45000,
                &clock,
                mint_for_testing<USD>(45000, ctx(&mut test)),
                ctx(&mut test)
            );
            assert!(coin::value(&base_coin) == 0, 0);
            assert!(coin::value(&quote_coin) == 45000, 0);
            burn_for_testing(base_coin);
            burn_for_testing(quote_coin);

            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user, 100000, 0);
            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user, 0, 100000);

            test::return_shared(clock);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        end(test)
    }

    // This test covers the following scenario:
    // there are some limit sell orders placed by invoking inject_limit_order
    // And directly perform the matching using the match_bid method.
    // When encountering self-matching, we should cancel all the oldest sell orders
    // and check if the order status in the order book and the user balance in the custodian account are correct.
    fun test_inject_and_match_taker_bid_with_skipping_self_matching_(mut test: Scenario): TransactionEffects {
        let (alice, _) = people();
        let owner = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(5000000, 2500000, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 10000;
            let alice_deposit_USDC: u64 = 10000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 1000, 1000, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 1 * FLOAT_SCALING, 10000, 10000, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        // test match (bid side)
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let (base_quantity_filled, quote_quantity_filled) = clob::test_match_bid(
                &mut pool,
                &account_cap,
                CLIENT_ID_ALICE,
                1,
                MAX_PRICE,
                0,
            );
            assert!(base_quantity_filled == 0, 0);
            assert!(quote_quantity_filled == 0, 0);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            custodian::assert_user_balance<SUI>(base_custodian, account_cap_user, 10000, 0);
            custodian::assert_user_balance<USD>(quote_custodian, account_cap_user, 0, 10000);
            let (next_bid_order_id, next_ask_order_id, _, _) = clob::get_pool_stat(&pool);
            assert!(next_bid_order_id == clob::order_id_for_test(1, true), 0);
            assert!(next_ask_order_id == clob::order_id_for_test(3, false), 0);
            {
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_empty_tick_level(asks, 2 * FLOAT_SCALING);
            };
            {
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_empty_tick_level(asks, 5 * FLOAT_SCALING);
            };
            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE,1 * FLOAT_SCALING, 10000, 10000, true, account_cap_user)
                );
                let (_, _, bid, _) = get_pool_stat(&pool);
                clob::check_tick_level(bid, 1 * FLOAT_SCALING, &open_orders);
            };
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        end(test)
    }

    // This test covers the following scenario:
    // there are some limit buy orders placed by invoking inject_limit_order
    // And  directly perform the matching using the match_ask method.
    // When encountering self-matching, we should cancel all the oldest buy orders
    // and check if the order status in the order book and the user balance in the custodian account are correct.
    fun test_inject_and_match_taker_ask_with_skipping_self_matching_(mut test: Scenario): TransactionEffects {
        let (alice, _) = people();
        let owner = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(5000000, 2500000, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 10000;
            let alice_deposit_USDC: u64 = 10000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        // test inject limit order and match (ask side)
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 500, 500, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 2 * FLOAT_SCALING, 1000, 1000, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 10 * FLOAT_SCALING, 10000, 10000, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        // test match (ask side)
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let (base_quantity_filled, quote_quantity_filled) = clob::test_match_ask(
                &mut pool,
                &account_cap,
                CLIENT_ID_ALICE,
                1500,
                MIN_PRICE,
                0,
            );
            assert!(base_quantity_filled == 0, 0);
            assert!(quote_quantity_filled == 0, 0);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            custodian::assert_user_balance<USD>(
                quote_custodian,
                account_cap_user,
                10000,
                0
            );
            custodian::assert_user_balance<SUI>(
                base_custodian,
                account_cap_user,
                0,
                10000
            );
            {
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_empty_tick_level(bids, 5 * FLOAT_SCALING);
            };
            {
                let (_, _, bids, _) = get_pool_stat(&pool);
                clob::check_empty_tick_level(bids, 2 * FLOAT_SCALING);
            };
            {
                let mut open_orders = vector::empty<Order>();
                vector::push_back(
                    &mut open_orders,
                    clob::test_construct_order(0, CLIENT_ID_ALICE, 10 * FLOAT_SCALING, 10000, 10000, false, account_cap_user)
                );
                let (_, _, _, asks) = get_pool_stat(&pool);
                clob::check_tick_level(asks, 10 * FLOAT_SCALING, &open_orders);
            };
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        end(test)
    }

    #[test]
    fun test_cancel_order_no_rounding(): TransactionEffects {
        let mut test = scenario();
        let (alice, bob) = people();
        let owner = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(0, 0, &mut test, owner);
        };
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let clock = test::take_shared<Clock>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 1000000000;
            let alice_deposit_USDC: u64 = 1000000000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            let(_, _) = custodian::account_balance(quote_custodian, account_cap_user);
            // Example buying 0.1 sui, for the price of .719
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 719000, 1000000000, 1000000000, true,
                CANCEL_OLDEST, &account_cap,ctx(&mut test));

            // Example selling 0.1 sui for the price of .519
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 519000, 1000000000, 1000000000, false,
                CANCEL_OLDEST, &account_cap,ctx(&mut test));
            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            clob::check_balance_invariants_for_account(&account_cap, quote_custodian, base_custodian, &pool);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, bob);
        // Buys some sui from alice
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let clock = test::take_shared<Clock>(&test);

            let (mut base_coin, mut quote_coin, _) = clob::swap_exact_base_for_quote(
                &mut pool,
                CLIENT_ID_BOB,
                &account_cap,
                100000,
                mint_for_testing<SUI>(100000000, ctx(&mut test)),
                mint_for_testing<USD>(0,  ctx(&mut test)),
                &clock,
                ctx(&mut test)
            );

            burn_for_testing(base_coin);
            burn_for_testing(quote_coin);

            // buy second time
            (base_coin, quote_coin, _) = clob::swap_exact_base_for_quote(
                &mut pool,
                CLIENT_ID_BOB,
                &account_cap,
                100000,
                mint_for_testing<SUI>(100000000, ctx(&mut test)),
                mint_for_testing<USD>(0,  ctx(&mut test)),
                &clock,
                ctx(&mut test)
            );

            burn_for_testing(base_coin);
            burn_for_testing(quote_coin);

            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            // cancel all order
            // clob::cancel_order<SUI, USD>(&mut pool, 1, &account_cap);
            // clob::cancel_all_orders<SUI, USD>(&mut pool, &account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            clob::check_balance_invariants_for_account(&account_cap, quote_custodian, base_custodian, &pool);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, bob);
        // Sells some USDC to alice
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let clock = test::take_shared<Clock>(&test);

            let (base_coin, quote_coin) = clob::place_market_order<SUI, USD>(
                &mut pool,
                &account_cap,
                CLIENT_ID_BOB,
                100000,
                true,
                mint_for_testing<SUI>(0, ctx(&mut test)),
                mint_for_testing<USD>(100000, ctx(&mut test)),
                &clock,
                ctx(&mut test)
            );

            burn_for_testing(base_coin);
            burn_for_testing(quote_coin);

            // buy second time
            let (base_coin, quote_coin) = clob::place_market_order<SUI, USD>(
                &mut pool,
                &account_cap,
                CLIENT_ID_BOB,
                100000,
                true,
                mint_for_testing<SUI>(0, ctx(&mut test)),
                mint_for_testing<USD>(100000, ctx(&mut test)),
                &clock,
                ctx(&mut test)
            );

            burn_for_testing(base_coin);
            burn_for_testing(quote_coin);


            // Buys but this time utilizes a different code path
            let (base_coin, quote_coin) = clob::place_market_order<SUI, USD>(
                &mut pool,
                &account_cap,
                CLIENT_ID_BOB,
                100000,
                false,
                mint_for_testing<SUI>(100000, ctx(&mut test)),
                mint_for_testing<USD>(0, ctx(&mut test)),
                &clock,
                ctx(&mut test)
            );

            burn_for_testing(base_coin);
            burn_for_testing(quote_coin);

            // buy second time
            let (base_coin, quote_coin) = clob::place_market_order<SUI, USD>(
                &mut pool,
                &account_cap,
                CLIENT_ID_BOB,
                100000,
                false,
                mint_for_testing<SUI>(100000, ctx(&mut test)),
                mint_for_testing<USD>(0, ctx(&mut test)),
                &clock,
                ctx(&mut test)
            );

            burn_for_testing(base_coin);
            burn_for_testing(quote_coin);

            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            clob::check_balance_invariants_for_account(&account_cap, quote_custodian, base_custodian, &pool);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, alice);
        // Check cancel all orders returns all funds
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            // cancel all order
            clob::cancel_all_orders<SUI, USD>(&mut pool, &account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            clob::check_balance_invariants_for_account(&account_cap, quote_custodian, base_custodian, &pool);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        end(test)
    }

    #[test]
    fun test_rounding_lock_order(): TransactionEffects {
        let mut test = scenario();
        let (alice, bob) = people();
        let alice2 = @0xCAFE;
        let owner = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(0, 0, &mut test, owner);
        };
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
            mint_account_cap_transfer(alice2, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let clock = test::take_shared<Clock>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 2000000000;
            let alice_deposit_USDC: u64 = 2000000000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            let(_, _) = custodian::account_balance(quote_custodian, account_cap_user);
            // Example buying 0.1 sui, for the price of .719
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 719000, 1000000000, 1000000000, true,
                CANCEL_OLDEST, &account_cap,ctx(&mut test));

            // alice's second bid order, which will be locked
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 718000, 1000000000, 1000000000, true,
                CANCEL_OLDEST, &account_cap,ctx(&mut test));

            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        next_tx(&mut test, bob);
        // Sell sui to alice, first rounding token cut in match_ask else clause
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let clock = test::take_shared<Clock>(&test);

            let (base_coin, quote_coin, _) = clob::swap_exact_base_for_quote(
                &mut pool,
                CLIENT_ID_BOB,
                &account_cap,
                100000,
                mint_for_testing<SUI>(100000000, ctx(&mut test)),
                mint_for_testing<USD>(0,  ctx(&mut test)),
                &clock,
                ctx(&mut test)
            );

            burn_for_testing(base_coin);
            burn_for_testing(quote_coin);

            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        next_tx(&mut test, alice);
        // alice self matching, second rounding token cut in match_ask if clause
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let clock = test::take_shared<Clock>(&test);

            let (base_coin, quote_coin, _) = clob::swap_exact_base_for_quote(
                &mut pool,
                CLIENT_ID_ALICE,
                &account_cap,
                100000,
                mint_for_testing<SUI>(100000000, ctx(&mut test)),
                mint_for_testing<USD>(0,  ctx(&mut test)),
                &clock,
                ctx(&mut test)
            );

            burn_for_testing(base_coin);
            burn_for_testing(quote_coin);

            test::return_shared(pool);
            test::return_shared(clock);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, alice);
        {
            let pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            clob::check_balance_invariants_for_account(&account_cap, quote_custodian, base_custodian, &pool);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        next_tx(&mut test, alice);
        // Check cancel all orders returns all funds
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            // cancel all order
            clob::cancel_all_orders<SUI, USD>(&mut pool, &account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_custodian(&pool);
            clob::check_balance_invariants_for_account(&account_cap, quote_custodian, base_custodian, &pool);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };
        end(test)
    }

    fun test_swap_exact_quote_for_base_with_metadata_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        let owner = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(5000000, 2500000, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 100000;
            let alice_deposit_USDC: u64 = 100000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 50000, 50000, false,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let clock = test::take_shared<Clock>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let (base_coin, quote_coin, _, of_events) = clob::swap_exact_quote_for_base_with_metadata(
                &mut pool,
                CLIENT_ID_BOB,
                &account_cap,
                50000,
                &clock,
                mint_for_testing<USD>(50000, ctx(&mut test)),
                ctx(&mut test)
            );

            let of_event = vector::borrow(&of_events, 0);
            let (_, _, is_bid, _, _, base_asset_quantity_filled, price, _ , _) = clob::matched_order_metadata_info(of_event);
            assert!(is_bid == false, 0);
            assert!(base_asset_quantity_filled == 9000, 0);
            assert!(price == 5 * FLOAT_SCALING, 0);

            burn_for_testing(base_coin);
            burn_for_testing(quote_coin);
            test::return_shared(clock);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        end(test)
    }

    fun test_swap_exact_base_for_quote_with_metadata_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        let owner = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(5000000, 2500000, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 100000;
            let alice_deposit_USDC: u64 = 100000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 5000, 5000, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let clock = test::take_shared<Clock>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let (base_coin, quote_coin, _, of_events) = clob::swap_exact_base_for_quote_with_metadata(
                &mut pool,
                CLIENT_ID_BOB,
                &account_cap,
                5000,
                mint_for_testing<SUI>(5000, ctx(&mut test)),
                mint_for_testing<USD>(0, ctx(&mut test)),
                &clock,
                ctx(&mut test)
            );

            let of_event = vector::borrow(&of_events, 0);
            let (_, _, is_bid, _, _, base_asset_quantity_filled, price, _ , _) = clob::matched_order_metadata_info(of_event);
            assert!(is_bid == true, 0);
            assert!(base_asset_quantity_filled == 5000, 0);
            assert!(price == 5 * FLOAT_SCALING, 0);

            burn_for_testing(base_coin);
            burn_for_testing(quote_coin);
            test::return_shared(clock);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        end(test)
    }

    fun test_place_market_order_with_metadata_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        let owner = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(5000000, 2500000, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 100000;
            let alice_deposit_USDC: u64 = 100000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 5000, 5000, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let clock = test::take_shared<Clock>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let (base_coin, quote_coin, of_events) = clob::place_market_order_with_metadata(
                &mut pool,
                &account_cap,
                CLIENT_ID_BOB,
                5000,
                false,
                mint_for_testing<SUI>(5000, ctx(&mut test)),
                mint_for_testing<USD>(0, ctx(&mut test)),
                &clock,
                ctx(&mut test)
            );

            let of_event = vector::borrow(&of_events, 0);
            let (_, _, is_bid, _, _, base_asset_quantity_filled, price, _ , _) = clob::matched_order_metadata_info(of_event);
            assert!(is_bid == true, 0);
            assert!(base_asset_quantity_filled == 5000, 0);
            assert!(price == 5 * FLOAT_SCALING, 0);

            burn_for_testing(base_coin);
            burn_for_testing(quote_coin);
            test::return_shared(clock);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        end(test)
    }

    fun test_place_limit_order_with_metadata_(mut test: Scenario): TransactionEffects {
        let (alice, bob) = people();
        let owner = @0xF;
        // setup pool and custodian
        next_tx(&mut test, owner);
        {
            clob::setup_test(5000000, 2500000, &mut test, owner);
        };
        next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(alice, test::ctx(&mut test));
        };
        next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(bob, test::ctx(&mut test));
        };
        next_tx(&mut test, alice);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            let (base_custodian, quote_custodian) = clob::borrow_mut_custodian(&mut pool);
            let alice_deposit_WSUI: u64 = 100000;
            let alice_deposit_USDC: u64 = 100000;
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_cap_user, alice_deposit_WSUI);
            custodian::test_increase_user_available_balance<USD>(quote_custodian, account_cap_user, alice_deposit_USDC);
            clob::test_inject_limit_order(&mut pool, CLIENT_ID_ALICE, 5 * FLOAT_SCALING, 5000, 5000, true,
                CANCEL_OLDEST, &account_cap, ctx(&mut test));
            test::return_shared(pool);
            test::return_to_address<AccountCap>(alice, account_cap);
        };

        next_tx(&mut test, bob);
        {
            let mut pool = test::take_shared<Pool<SUI, USD>>(&test);
            let clock = test::take_shared<Clock>(&test);
            let account_cap = test::take_from_address<AccountCap>(&test, bob);
            let bob_deposit_WSUI: u64 = 100000;
            let (base_custodian, _) = clob::borrow_mut_custodian(&mut pool);
            custodian::test_increase_user_available_balance<SUI>(base_custodian, account_owner(&account_cap), bob_deposit_WSUI);
            let (_, _, _, _, of_events) = clob::place_limit_order_with_metadata(
                &mut pool,
                CLIENT_ID_BOB,
                5 * FLOAT_SCALING,
                5000,
                CANCEL_OLDEST,
                false,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                ctx(&mut test)
            );

            let of_event = vector::borrow(&of_events, 0);
            let (_, _, is_bid, _, _, base_asset_quantity_filled, price, _ , _) = clob::matched_order_metadata_info(of_event);
            assert!(is_bid == true, 0);
            assert!(base_asset_quantity_filled == 5000, 0);
            assert!(price == 5 * FLOAT_SCALING, 0);

            test::return_shared(clock);
            test::return_shared(pool);
            test::return_to_address<AccountCap>(bob, account_cap);
        };
        end(test)
    }

    fun scenario(): Scenario { test::begin(@0x1) }

    fun people(): (address, address) { (@0xBEEF, @0x1337) }
}
