// Copyright (c) Mysten Labs, Inc.
// SPDX-License-Identifier: Apache-2.0

#[test_only]
module deepbook::order_query_tests {
    use std::option::{none, some};
    use sui::clock;
    use deepbook::order_query;
    use deepbook::order_query::iter_bids;
    use deepbook::custodian_v2;
    use deepbook::custodian_v2::{AccountCap, account_owner};
    use sui::clock::Clock;
    use sui::coin::mint_for_testing;
    use deepbook::clob_v2;
    use sui::sui::SUI;
    use deepbook::clob_v2::{setup_test, USD, mint_account_cap_transfer, Pool};
    use sui::test_scenario;
    use sui::test_scenario::{next_tx, end, ctx, Scenario};

    const CLIENT_ID_ALICE: u64 = 0;
    const FLOAT_SCALING: u64 = 1000000000;
    const CANCEL_OLDEST: u8 = 0;
    const TIMESTAMP_INF: u64 = (1u128 << 64 - 1) as u64;

    const OWNER: address = @0xf;
    const ALICE: address = @0xBEEF;
    const BOB: address = @0x1337;

    #[test]
    fun test_order_query_pagination() {
        let mut scenario = prepare_scenario();
        add_orders(200, TIMESTAMP_INF, none(), &mut scenario);
        let pool = test_scenario::take_shared<Pool<SUI, USD>>(&scenario);
        let page1 = iter_bids(&pool, none(), none(), none(), none(), true);
        assert!(vector::length(order_query::orders(&page1)) == 100, 0);
        assert!(order_query::has_next_page(&page1), 0);

        let orders = order_query::orders(&page1);
        let first_order = vector::borrow(orders, 0);
        assert!(order_query::order_id(first_order) == 1, 0);
        let last_order = vector::borrow(orders, vector::length(orders) - 1);

        assert!(order_query::order_id(last_order) == 100, 0);

        let page2 = iter_bids(
            &pool,
            order_query::next_tick_level(&page1),
            order_query::next_order_id(&page1),
            none(),
            none(),
            true
        );
        assert!(vector::length(order_query::orders(&page2)) == 100, 0);
        assert!(!order_query::has_next_page(&page2), 0);

        let orders = order_query::orders(&page2);
        let first_order = vector::borrow(orders, 0);
        assert!(order_query::order_id(first_order) == 101, 0);
        let last_order = vector::borrow(orders, vector::length(orders) - 1);
        assert!(order_query::order_id(last_order) == 200, 0);

        test_scenario::return_shared(pool);
        end(scenario);
    }

    #[test]
    fun test_order_query_pagination_decending() {
        let mut scenario = prepare_scenario();
        add_orders(200, TIMESTAMP_INF, none(), &mut scenario);
        let pool = test_scenario::take_shared<Pool<SUI, USD>>(&scenario);
        let page1 = iter_bids(&pool, none(), none(), none(), none(), false);

        assert!(vector::length(order_query::orders(&page1)) == 100, 0);
        assert!(order_query::has_next_page(&page1), 0);

        let orders = order_query::orders(&page1);
        let first_order = vector::borrow(orders, 0);
        assert!(order_query::order_id(first_order) == 200, 0);
        let last_order = vector::borrow(orders, vector::length(orders) - 1);

        assert!(order_query::order_id(last_order) == 101, 0);

        let page2 = iter_bids(
            &pool,
            order_query::next_tick_level(&page1),
            order_query::next_order_id(&page1),
            none(),
            none(),
            false
        );
        assert!(vector::length(order_query::orders(&page2)) == 100, 0);
        assert!(!order_query::has_next_page(&page2), 0);

        let orders = order_query::orders(&page2);
        let first_order = vector::borrow(orders, 0);
        assert!(order_query::order_id(first_order) == 100, 0);
        let last_order = vector::borrow(orders, vector::length(orders) - 1);
        assert!(order_query::order_id(last_order) == 1, 0);

        test_scenario::return_shared(pool);
        end(scenario);
    }

    #[test]
    fun test_order_query_start_order_id() {
        let mut scenario = prepare_scenario();
        add_orders(200, TIMESTAMP_INF, none(), &mut scenario);
        let pool = test_scenario::take_shared<Pool<SUI, USD>>(&scenario);
        // test start order id
        let page = iter_bids(&pool, none(), some(51), none(), none(), true);
        assert!(vector::length(order_query::orders(&page)) == 100, 0);
        assert!(order_query::has_next_page(&page), 0);

        let orders = order_query::orders(&page);
        let first_order = vector::borrow(orders, 0);
        assert!(order_query::order_id(first_order) == 51, 0);
        let last_order = vector::borrow(orders, vector::length(orders) - 1);
        assert!(order_query::order_id(last_order) == 150, 0);

        let page2 = iter_bids(
            &pool,
            order_query::next_tick_level(&page),
            order_query::next_order_id(&page),
            none(),
            none(),
            true
        );
        assert!(vector::length(order_query::orders(&page2)) == 50, 0);
        assert!(!order_query::has_next_page(&page2), 0);

        let orders = order_query::orders(&page2);

        let first_order = vector::borrow(orders, 0);
        assert!(order_query::order_id(first_order) == 151, 0);
        let last_order = vector::borrow(orders, vector::length(orders) - 1);
        assert!(order_query::order_id(last_order) == 200, 0);

        test_scenario::return_shared(pool);
        end(scenario);
    }

    #[test]
    fun test_order_query_with_expiry() {
        let mut scenario = prepare_scenario();
        add_orders(20, TIMESTAMP_INF, none(), &mut scenario);

        let clock = test_scenario::take_shared<Clock>(&scenario);
        let expired_timestamp = clock::timestamp_ms(&clock) + 10000;
        test_scenario::return_shared(clock);
        next_tx(&mut scenario, ALICE);

        add_orders(50, expired_timestamp, none(), &mut scenario);

        let pool = test_scenario::take_shared<Pool<SUI, USD>>(&scenario);

        // test get all order excluding expired orders
        let page = iter_bids(&pool, none(), none(), some(expired_timestamp + 1), none(), true);
        assert!(vector::length(order_query::orders(&page)) == 20, 0);
        assert!(!order_query::has_next_page(&page), 0);

        let orders = order_query::orders(&page);
        let first_order = vector::borrow(orders, 0);
        assert!(order_query::order_id(first_order) == 1, 0);
        let last_order = vector::borrow(orders, vector::length(orders) - 1);
        assert!(order_query::order_id(last_order) == 20, 0);

        test_scenario::return_shared(pool);
        end(scenario);
    }

    #[test]
    fun test_order_query_with_max_id() {
        let mut scenario = prepare_scenario();
        add_orders(70, TIMESTAMP_INF, none(), &mut scenario);

        let pool = test_scenario::take_shared<Pool<SUI, USD>>(&scenario);

        // test get all order with id < 50
        let page = iter_bids(&pool, none(), none(), none(), some(50), true);
        assert!(vector::length(order_query::orders(&page)) == 50, 0);
        assert!(!order_query::has_next_page(&page), 0);

        let orders = order_query::orders(&page);
        let first_order = vector::borrow(orders, 0);
        assert!(order_query::order_id(first_order) == 1, 0);
        let last_order = vector::borrow(orders, vector::length(orders) - 1);
        assert!(order_query::order_id(last_order) == 50, 0);

        // test get all order with id between 20 and 50
        let page = iter_bids(&pool, none(), some(20), none(), some(50), true);

        assert!(vector::length(order_query::orders(&page)) == 31, 0);
        assert!(!order_query::has_next_page(&page), 0);

        let orders = order_query::orders(&page);
        let first_order = vector::borrow(orders, 0);
        assert!(order_query::order_id(first_order) == 20, 0);
        let last_order = vector::borrow(orders, vector::length(orders) - 1);
        assert!(order_query::order_id(last_order) == 50, 0);

        test_scenario::return_shared(pool);
        end(scenario);
    }

    #[test]
    fun test_order_query_pagination_multiple_orders_same_tick_level() {
        let mut scenario = prepare_scenario();
        // orders with same tick level repeated 4 times
        add_orders(50, TIMESTAMP_INF, none(), &mut scenario);
        add_orders(50, TIMESTAMP_INF, none(), &mut scenario);
        add_orders(50, TIMESTAMP_INF, none(), &mut scenario);
        add_orders(50, TIMESTAMP_INF, none(), &mut scenario);

        let pool = test_scenario::take_shared<Pool<SUI, USD>>(&scenario);
        let page1 = iter_bids(&pool, none(), none(), none(), none(), true);
        assert!(vector::length(order_query::orders(&page1)) == 100, 0);
        assert!(order_query::has_next_page(&page1), 0);

        let orders = order_query::orders(&page1);
        let first_order = vector::borrow(orders, 0);
        assert!(order_query::order_id(first_order) == 1, 0);
        let last_order = vector::borrow(orders, vector::length(orders) - 1);
        assert!(order_query::order_id(last_order) == 175, 0);

        let page2 = iter_bids(
            &pool,
            order_query::next_tick_level(&page1),
            order_query::next_order_id(&page1),
            none(),
            none(),
            true
        );
        assert!(vector::length(order_query::orders(&page2)) == 100, 0);
        assert!(!order_query::has_next_page(&page2), 0);

        let orders = order_query::orders(&page2);
        let first_order = vector::borrow(orders, 0);
        assert!(order_query::order_id(first_order) == 26, 0);
        let last_order = vector::borrow(orders, vector::length(orders) - 1);
        assert!(order_query::order_id(last_order) == 200, 0);

        // Query order with tick level > 40 * FLOAT_SCALING
        let page = iter_bids(&pool, some(40 * FLOAT_SCALING), none(), none(), none(), true);

        // should only contain orders with tick level > 40 - 50, 44 orders in total
        assert!(vector::length(order_query::orders(&page)) == 44, 0);
        assert!(!order_query::has_next_page(&page), 0);

        let orders = order_query::orders(&page);
        let first_order = vector::borrow(orders, 0);
        assert!(order_query::order_id(first_order) == 40, 0);
        let last_order = vector::borrow(orders, vector::length(orders) - 1);
        assert!(order_query::order_id(last_order) == 200, 0);

        test_scenario::return_shared(pool);
        end(scenario);
    }

    #[test]
    fun test_query_after_insert() {
        let mut scenario = prepare_scenario();
        add_orders(200, TIMESTAMP_INF, none(), &mut scenario);

        // insert a new order at tick level 10
        add_orders(1, TIMESTAMP_INF, some(10), &mut scenario);

        let pool = test_scenario::take_shared<Pool<SUI, USD>>(&scenario);
        let page = iter_bids(&pool, some(11 * FLOAT_SCALING), none(), none(), none(), true);

        // this page should start from order id 11 and end at order id 110, contains 100 orders
        assert!(vector::length(order_query::orders(&page)) == 100, 0);
        assert!(order_query::has_next_page(&page), 0);

        let orders = order_query::orders(&page);
        let first_order = vector::borrow(orders, 0);
        assert!(order_query::order_id(first_order) == 11, 0);
        let last_order = vector::borrow(orders, vector::length(orders) - 1);
        assert!(order_query::order_id(last_order) == 110, 0);

        // tick 10 should contain 2 orders
        let page2 = iter_bids(&pool, some(10 * FLOAT_SCALING), none(), none(), none(), true);
        let orders = order_query::orders(&page2);
        let first_order = vector::borrow(orders, 0);
        assert!(order_query::tick_level(first_order) == 10 * FLOAT_SCALING, 0);
        let second_order = vector::borrow(orders, 1);
        assert!(order_query::tick_level(second_order) == 10 * FLOAT_SCALING, 0);
        let third_order = vector::borrow(orders, 2);
        assert!(order_query::tick_level(third_order) == 11 * FLOAT_SCALING, 0);

        test_scenario::return_shared(pool);
        end(scenario);
    }

    fun prepare_scenario(): Scenario {
        let mut scenario = test_scenario::begin(@0x1);
        next_tx(&mut scenario, OWNER);
        setup_test(5000000, 2500000, &mut scenario, OWNER);

        next_tx(&mut scenario, ALICE);
        mint_account_cap_transfer(ALICE, test_scenario::ctx(&mut scenario));
        next_tx(&mut scenario, BOB);
        mint_account_cap_transfer(BOB, test_scenario::ctx(&mut scenario));
        next_tx(&mut scenario, ALICE);

        let mut pool = test_scenario::take_shared<Pool<SUI, USD>>(&scenario);
        let account_cap = test_scenario::take_from_sender<AccountCap>(&scenario);
        let account_cap_user = account_owner(&account_cap);
        let (base_custodian, quote_custodian) = clob_v2::borrow_mut_custodian(&mut pool);
        custodian_v2::deposit(base_custodian, mint_for_testing<SUI>(10000000, ctx(&mut scenario)), account_cap_user);
        custodian_v2::deposit(
            quote_custodian,
            mint_for_testing<USD>(100000000, ctx(&mut scenario)),
            account_cap_user
        );
        test_scenario::return_shared(pool);
        test_scenario::return_to_sender<AccountCap>(&scenario, account_cap);
        next_tx(&mut scenario, ALICE);
        scenario
    }

    fun add_orders(order_count: u64, timestamp: u64, price: Option<u64>, scenario: &mut Scenario) {
        let mut n = 1;
        while (n <= order_count) {
            let price = if (option::is_some(&price)) {
                option::destroy_some(price) * FLOAT_SCALING
            } else {
                n * FLOAT_SCALING
            };

            let account_cap = test_scenario::take_from_sender<AccountCap>(scenario);
            let mut pool = test_scenario::take_shared<Pool<SUI, USD>>(scenario);
            let clock = test_scenario::take_shared<Clock>(scenario);
            clob_v2::place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                price,
                2000,
                CANCEL_OLDEST,
                true,
                timestamp,
                0,
                &clock,
                &account_cap,
                ctx(scenario)
            );
            n = n + 1;
            test_scenario::return_shared(clock);
            test_scenario::return_shared(pool);
            test_scenario::return_to_address<AccountCap>(ALICE, account_cap);
            next_tx(scenario, ALICE);
        };
    }
}
