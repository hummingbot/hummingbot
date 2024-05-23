// Copyright (c) Mysten Labs, Inc.
// SPDX-License-Identifier: Apache-2.0

module deepbook::order_query {
    use std::option::{some, none};
    use deepbook::critbit::CritbitTree;
    use sui::linked_table;
    use deepbook::critbit;
    use deepbook::clob_v2;
    use deepbook::clob_v2::{Order, Pool, TickLevel};

    const PAGE_LIMIT: u64 = 100;

    public struct OrderPage has drop {
        orders: vector<Order>,
        // false if this is the last page
        has_next_page: bool,
        // tick level where the next page begins (if any)
        next_tick_level: Option<u64>,
        // order id where the next page begins (if any)
        next_order_id: Option<u64>
    }

    // return an OrderPage starting from start_tick_level + start_order_id
    // containing as many orders as possible without going over the
    // dynamic fields accessed/tx limit
    public fun iter_bids<T1, T2>(
        pool: &Pool<T1, T2>,
        // tick level to start from
        start_tick_level: Option<u64>,
        // order id within that tick level to start from
        start_order_id: Option<u64>,
        // if provided, do not include orders with an expire timestamp less than the provided value (expired order),
        // value is in microseconds
        min_expire_timestamp: Option<u64>,
        // do not show orders with an ID larger than max_id--
        // i.e., orders added later than this one
        max_id: Option<u64>,
        // if true, the orders are returned in ascending tick level.
        ascending: bool,
    ): OrderPage {
        let bids = clob_v2::bids(pool);
        let mut orders = iter_ticks_internal(
            bids,
            start_tick_level,
            start_order_id,
            min_expire_timestamp,
            max_id,
            ascending
        );
        let (orders, has_next_page, next_tick_level, next_order_id) = if (vector::length(&orders) > PAGE_LIMIT) {
            let last_order = vector::pop_back(&mut orders);
            (orders, true, some(clob_v2::tick_level(&last_order)), some(clob_v2::order_id(&last_order)))
        } else {
            (orders, false, none(), none())
        };

        OrderPage {
            orders,
            has_next_page,
            next_tick_level,
            next_order_id
        }
    }

    public fun iter_asks<T1, T2>(
        pool: &Pool<T1, T2>,
        // tick level to start from
        start_tick_level: Option<u64>,
        // order id within that tick level to start from
        start_order_id: Option<u64>,
        // if provided, do not include orders with an expire timestamp less than the provided value (expired order),
        // value is in microseconds
        min_expire_timestamp: Option<u64>,
        // do not show orders with an ID larger than max_id--
        // i.e., orders added later than this one
        max_id: Option<u64>,
        // if true, the orders are returned in ascending tick level.
        ascending: bool,
    ): OrderPage {
        let asks = clob_v2::asks(pool);
        let mut orders = iter_ticks_internal(
            asks,
            start_tick_level,
            start_order_id,
            min_expire_timestamp,
            max_id,
            ascending
        );
        let (orders, has_next_page, next_tick_level, next_order_id) = if (vector::length(&orders) > PAGE_LIMIT) {
            let last_order = vector::pop_back(&mut orders);
            (orders, true, some(clob_v2::tick_level(&last_order)), some(clob_v2::order_id(&last_order)))
        } else {
            (orders, false, none(), none())
        };

        OrderPage {
            orders,
            has_next_page,
            next_tick_level,
            next_order_id
        }
    }

    fun iter_ticks_internal(
        ticks: &CritbitTree<TickLevel>,
        // tick level to start from
        start_tick_level: Option<u64>,
        // order id within that tick level to start from
        mut start_order_id: Option<u64>,
        // if provided, do not include orders with an expire timestamp less than the provided value (expired order),
        // value is in microseconds
        min_expire_timestamp: Option<u64>,
        // do not show orders with an ID larger than max_id--
        // i.e., orders added later than this one
        max_id: Option<u64>,
        // if true, the orders are returned in ascending tick level.
        ascending: bool,
    ): vector<Order> {
        let mut tick_level_key = if (option::is_some(&start_tick_level)) {
            option::destroy_some(start_tick_level)
        } else {
            let (key, _) = if (ascending) {
                critbit::min_leaf(ticks)
            }else {
                critbit::max_leaf(ticks)
            };
            key
        };

        let mut orders = vector[];

        while (tick_level_key != 0 && vector::length(&orders) < PAGE_LIMIT + 1) {
            let tick_level = critbit::borrow_leaf_by_key(ticks, tick_level_key);
            let open_orders = clob_v2::open_orders(tick_level);

            let mut next_order_key = if (option::is_some(&start_order_id)) {
                let key = option::destroy_some(start_order_id);
                if (!linked_table::contains(open_orders, key)) {
                    let (next_leaf, _) = if (ascending) {
                        critbit::next_leaf(ticks, tick_level_key)
                    }else {
                        critbit::previous_leaf(ticks, tick_level_key)
                    };
                    tick_level_key = next_leaf;
                    continue
                };
                start_order_id = option::none();
                some(key)
            }else {
                *linked_table::front(open_orders)
            };

            while (option::is_some(&next_order_key) && vector::length(&orders) < PAGE_LIMIT + 1) {
                let key = option::destroy_some(next_order_key);
                let order = linked_table::borrow(open_orders, key);

                // if the order id is greater than max_id, we end the iteration for this tick level.
                if (option::is_some(&max_id) && key > option::destroy_some(max_id)) {
                    break
                };

                next_order_key = *linked_table::next(open_orders, key);

                // if expire timestamp is set, and if the order is expired, we skip it.
                if (option::is_none(&min_expire_timestamp) ||
                    clob_v2::expire_timestamp(order) > option::destroy_some(min_expire_timestamp)) {
                    vector::push_back(&mut orders, clob_v2::clone_order(order));
                };
            };
            let (next_leaf, _) = if (ascending) {
                critbit::next_leaf(ticks, tick_level_key)
            }else {
                critbit::previous_leaf(ticks, tick_level_key)
            };
            tick_level_key = next_leaf;
        };
        orders
    }

    public fun orders(page: &OrderPage): &vector<Order> {
        &page.orders
    }

    public fun has_next_page(page: &OrderPage): bool {
        page.has_next_page
    }

    public fun next_tick_level(page: &OrderPage): Option<u64> {
        page.next_tick_level
    }

    public fun next_order_id(page: &OrderPage): Option<u64> {
        page.next_order_id
    }

    public fun order_id(order: &Order): u64 {
        clob_v2::order_id(order)
    }

    public fun tick_level(order: &Order): u64 {
        clob_v2::tick_level(order)
    }
}
