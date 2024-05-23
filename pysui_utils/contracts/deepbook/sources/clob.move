// Copyright (c) Mysten Labs, Inc.
// SPDX-License-Identifier: Apache-2.0

#[allow(unused_use)]
module deepbook::clob {
    use std::type_name::{Self, TypeName};

    use sui::balance::{Self, Balance};
    use sui::clock::{Self, Clock};
    use sui::coin::{Self, Coin, join};
    use sui::event;
    use sui::linked_table::{Self, LinkedTable};
    use sui::sui::SUI;
    use sui::table::{Self, Table, contains, add, borrow_mut};

    use deepbook::critbit::{Self, CritbitTree, is_empty, borrow_mut_leaf_by_index, min_leaf, remove_leaf_by_index, max_leaf, next_leaf, previous_leaf, borrow_leaf_by_index, borrow_leaf_by_key, find_leaf, insert_leaf};
    use deepbook::custodian::{Self, Custodian, AccountCap};
    use deepbook::math::Self as clob_math;

    // <<<<<<<<<<<<<<<<<<<<<<<< Error codes <<<<<<<<<<<<<<<<<<<<<<<<
    const DEPRECATED: u64 = 0;
    #[test_only]
    const EInvalidFeeRateRebateRate: u64 = 2;
    const EInvalidOrderId: u64 = 3;
    const EUnauthorizedCancel: u64 = 4;
    const EInvalidPrice: u64 = 5;
    const EInvalidQuantity: u64 = 6;
    // Insufficient amount of base coin.
    const EInsufficientBaseCoin: u64 = 7;
    // Insufficient amount of quote coin.
    const EInsufficientQuoteCoin: u64 = 8;
    const EOrderCannotBeFullyFilled: u64 = 9;
    const EOrderCannotBeFullyPassive: u64 = 10;
    const EInvalidTickPrice: u64 = 11;
    const EInvalidUser: u64 = 12;
    #[test_only]
    const ENotEqual: u64 = 13;
    const EInvalidRestriction: u64 = 14;
    #[test_only]
    const EInvalidPair: u64 = 16;
    const EInvalidExpireTimestamp: u64 = 19;
    #[test_only]
    const EInvalidTickSizeLotSize: u64 = 20;

    // <<<<<<<<<<<<<<<<<<<<<<<< Error codes <<<<<<<<<<<<<<<<<<<<<<<<

    // <<<<<<<<<<<<<<<<<<<<<<<< Constants <<<<<<<<<<<<<<<<<<<<<<<<
    const FLOAT_SCALING: u64 = 1_000_000_000;
    // Restrictions on limit orders.
    const NO_RESTRICTION: u8 = 0;
    // Mandates that whatever amount of an order that can be executed in the current transaction, be filled and then the rest of the order canceled.
    const IMMEDIATE_OR_CANCEL: u8 = 1;
    // Mandates that the entire order size be filled in the current transaction. Otherwise, the order is canceled.
    const FILL_OR_KILL: u8 = 2;
    // Mandates that the entire order be passive. Otherwise, cancel the order.
    const POST_OR_ABORT: u8 = 3;
    #[test_only]
    const MIN_BID_ORDER_ID: u64 = 1;
    const MIN_ASK_ORDER_ID: u64 = 1 << 63;
    const MIN_PRICE: u64 = 0;
    const MAX_PRICE: u64 = (1u128 << 64 - 1) as u64;
    #[test_only]
    const TIMESTAMP_INF: u64 = (1u128 << 64 - 1) as u64;
    #[test_only]
    const FEE_AMOUNT_FOR_CREATE_POOL: u64 = 100 * 1_000_000_000; // 100 SUI

    // <<<<<<<<<<<<<<<<<<<<<<<< Constants <<<<<<<<<<<<<<<<<<<<<<<<

    // <<<<<<<<<<<<<<<<<<<<<<<< Events <<<<<<<<<<<<<<<<<<<<<<<<

    #[allow(unused_field)]
    /// Emitted when a new pool is created
    public struct PoolCreated has copy, store, drop {
        /// object ID of the newly created pool
        pool_id: ID,
        base_asset: TypeName,
        quote_asset: TypeName,
        taker_fee_rate: u64,
        // 10^9 scaling
        maker_rebate_rate: u64,
        tick_size: u64,
        lot_size: u64,
    }

    /// Emitted when a maker order is injected into the order book.
    public struct OrderPlacedV2<phantom BaseAsset, phantom QuoteAsset> has copy, store, drop {
        /// object ID of the pool the order was placed on
        pool_id: ID,
        /// ID of the order within the pool
        order_id: u64,
        is_bid: bool,
        /// object ID of the `AccountCap` that placed the order
        owner: ID,
        base_asset_quantity_placed: u64,
        price: u64,
        expire_timestamp: u64
    }

    /// Emitted when a maker order is canceled.
    public struct OrderCanceled<phantom BaseAsset, phantom QuoteAsset> has copy, store, drop {
        /// object ID of the pool the order was placed on
        pool_id: ID,
        /// ID of the order within the pool
        order_id: u64,
        is_bid: bool,
        /// object ID of the `AccountCap` that placed the order
        owner: ID,
        base_asset_quantity_canceled: u64,
        price: u64
    }

    /// Emitted only when a maker order is filled.
    public struct OrderFilledV2<phantom BaseAsset, phantom QuoteAsset> has copy, store, drop {
        /// object ID of the pool the order was placed on
        pool_id: ID,
        /// ID of the order within the pool
        order_id: u64,
        is_bid: bool,
        /// object ID of the `AccountCap` that placed the order
        owner: ID,
        total_quantity: u64,
        base_asset_quantity_filled: u64,
        base_asset_quantity_remaining: u64,
        price: u64,
        taker_commission: u64,
        maker_rebates: u64
    }
    // <<<<<<<<<<<<<<<<<<<<<<<< Events <<<<<<<<<<<<<<<<<<<<<<<<

    public struct Order has store, drop {
        // For each pool, order id is incremental and unique for each opening order.
        // Orders that are submitted earlier has lower order ids.
        // 64 bits are sufficient for order ids whereas 32 bits are not.
        // Assuming a maximum TPS of 100K/s of Sui chain, it would take (1<<63) / 100000 / 3600 / 24 / 365 = 2924712 years to reach the full capacity.
        // The highest bit of the order id is used to denote the order tyep, 0 for bid, 1 for ask.
        order_id: u64,
        // Only used for limit orders.
        price: u64,
        quantity: u64,
        is_bid: bool,
        // Order can only be cancelled by the owner.
        owner: ID,
        // Expiration timestamp in ms.
        expire_timestamp: u64,
    }

    public struct TickLevel has store {
        price: u64,
        // The key is order order id.
        open_orders: LinkedTable<u64, Order>,
        // other price level info
    }

    #[allow(unused_field)]
    public struct Pool<phantom BaseAsset, phantom QuoteAsset> has key {
        // The key to the following Critbit Tree are order prices.
        id: UID,
        // All open bid orders.
        bids: CritbitTree<TickLevel>,
        // All open ask orders.
        asks: CritbitTree<TickLevel>,
        // Order id of the next bid order, starting from 0.
        next_bid_order_id: u64,
        // Order id of the next ask order, starting from 1<<63.
        next_ask_order_id: u64,
        // Map from user id -> (map from order id -> order price)
        usr_open_orders: Table<ID, LinkedTable<u64, u64>>,
        // taker_fee_rate should be strictly greater than maker_rebate_rate.
        // The difference between taker_fee_rate and maker_rabate_rate goes to the protocol.
        // 10^9 scaling
        taker_fee_rate: u64,
        // 10^9 scaling
        maker_rebate_rate: u64,
        tick_size: u64,
        lot_size: u64,
        // other pool info
        base_custodian: Custodian<BaseAsset>,
        quote_custodian: Custodian<QuoteAsset>,
        // Stores the fee paid to create this pool. These funds are not accessible.
        creation_fee: Balance<SUI>,
        // Deprecated.
        base_asset_trading_fees: Balance<BaseAsset>,
        // Stores the trading fees paid in `QuoteAsset`. These funds are not accessible.
        quote_asset_trading_fees: Balance<QuoteAsset>,
    }

    fun destroy_empty_level(level: TickLevel) {
        let TickLevel {
            price: _,
            open_orders: orders,
        } = level;

        linked_table::destroy_empty(orders);
    }

    public fun create_account(_ctx: &mut TxContext): AccountCap {
        abort DEPRECATED
    }

    #[test_only]
    fun create_pool_<BaseAsset, QuoteAsset>(
        taker_fee_rate: u64,
        maker_rebate_rate: u64,
        tick_size: u64,
        lot_size: u64,
        creation_fee: Balance<SUI>,
        ctx: &mut TxContext,
    ) {
        let base_type_name = type_name::get<BaseAsset>();
        let quote_type_name = type_name::get<QuoteAsset>();

        assert!(clob_math::unsafe_mul(lot_size, tick_size) > 0, EInvalidTickSizeLotSize);
        assert!(base_type_name != quote_type_name, EInvalidPair);
        assert!(taker_fee_rate >= maker_rebate_rate, EInvalidFeeRateRebateRate);

        let pool_uid = object::new(ctx);
        let pool_id = *object::uid_as_inner(&pool_uid);
        transfer::share_object(
            Pool<BaseAsset, QuoteAsset> {
                id: pool_uid,
                bids: critbit::new(ctx),
                asks: critbit::new(ctx),
                next_bid_order_id: MIN_BID_ORDER_ID,
                next_ask_order_id: MIN_ASK_ORDER_ID,
                usr_open_orders: table::new(ctx),
                taker_fee_rate,
                maker_rebate_rate,
                tick_size,
                lot_size,
                base_custodian: custodian::new<BaseAsset>(ctx),
                quote_custodian: custodian::new<QuoteAsset>(ctx),
                creation_fee,
                base_asset_trading_fees: balance::zero(),
                quote_asset_trading_fees: balance::zero(),
            }
        );
        event::emit(PoolCreated {
            pool_id,
            base_asset: base_type_name,
            quote_asset: quote_type_name,
            taker_fee_rate,
            maker_rebate_rate,
            tick_size,
            lot_size,
        })
    }

    #[allow(unused_type_parameter)]
    public fun create_pool<BaseAsset, QuoteAsset>(
        _tick_size: u64,
        _lot_size: u64,
        _creation_fee: Coin<SUI>,
        _ctx: &mut TxContext,
    ) {
        abort DEPRECATED
    }

    public fun deposit_base<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        coin: Coin<BaseAsset>,
        account_cap: &AccountCap
    ) {
        assert!(coin::value(&coin) != 0, EInsufficientBaseCoin);
        custodian::increase_user_available_balance(
            &mut pool.base_custodian,
            object::id(account_cap),
            coin::into_balance(coin)
        )
    }

    public fun deposit_quote<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        coin: Coin<QuoteAsset>,
        account_cap: &AccountCap
    ) {
        assert!(coin::value(&coin) != 0, EInsufficientQuoteCoin);
        custodian::increase_user_available_balance(
            &mut pool.quote_custodian,
            object::id(account_cap),
            coin::into_balance(coin)
        )
    }

    public fun withdraw_base<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        quantity: u64,
        account_cap: &AccountCap,
        ctx: &mut TxContext
    ): Coin<BaseAsset> {
        assert!(quantity > 0, EInvalidQuantity);
        custodian::withdraw_asset(&mut pool.base_custodian, quantity, account_cap, ctx)
    }

    public fun withdraw_quote<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        quantity: u64,
        account_cap: &AccountCap,
        ctx: &mut TxContext
    ): Coin<QuoteAsset> {
        assert!(quantity > 0, EInvalidQuantity);
        custodian::withdraw_asset(&mut pool.quote_custodian, quantity, account_cap, ctx)
    }

    // for smart routing
    public fun swap_exact_base_for_quote<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        quantity: u64,
        base_coin: Coin<BaseAsset>,
        quote_coin: Coin<QuoteAsset>,
        clock: &Clock,
        ctx: &mut TxContext,
    ): (Coin<BaseAsset>, Coin<QuoteAsset>, u64) {
        assert!(quantity > 0, EInvalidQuantity);
        assert!(coin::value(&base_coin) >= quantity, EInsufficientBaseCoin);
        let original_val = coin::value(&quote_coin);
        let (ret_base_coin, ret_quote_coin) = place_market_order(
            pool,
            quantity,
            false,
            base_coin,
            quote_coin,
            clock,
            ctx
        );
        let ret_val = coin::value(&ret_quote_coin);
        (ret_base_coin, ret_quote_coin, ret_val - original_val)
    }

    // for smart routing
    public fun swap_exact_quote_for_base<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        quantity: u64,
        clock: &Clock,
        quote_coin: Coin<QuoteAsset>,
        ctx: &mut TxContext,
    ): (Coin<BaseAsset>, Coin<QuoteAsset>, u64) {
        assert!(quantity > 0, EInvalidQuantity);
        assert!(coin::value(&quote_coin) >= quantity, EInsufficientQuoteCoin);
        let (base_asset_balance, quote_asset_balance) = match_bid_with_quote_quantity(
            pool,
            quantity,
            MAX_PRICE,
            clock::timestamp_ms(clock),
            coin::into_balance(quote_coin)
        );
        let val = balance::value(&base_asset_balance);
        (coin::from_balance(base_asset_balance, ctx), coin::from_balance(quote_asset_balance, ctx), val)
    }

    fun match_bid_with_quote_quantity<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        quantity: u64,
        price_limit: u64,
        current_timestamp: u64,
        quote_balance: Balance<QuoteAsset>,
    ): (Balance<BaseAsset>, Balance<QuoteAsset>) {
        // Base balance received by taker, taking into account of taker commission.
        // Need to individually keep track of the remaining base quantity to be filled to avoid infinite loop.
        let pool_id = *object::uid_as_inner(&pool.id);
        let mut taker_quote_quantity_remaining = quantity;
        let mut base_balance_filled = balance::zero<BaseAsset>();
        let mut quote_balance_left = quote_balance;
        let all_open_orders = &mut pool.asks;
        if (critbit::is_empty(all_open_orders)) {
            return (base_balance_filled, quote_balance_left)
        };
        let (mut tick_price, mut tick_index) = min_leaf(all_open_orders);
        let mut terminate_loop = false;

        while (!is_empty<TickLevel>(all_open_orders) && tick_price <= price_limit) {
            let tick_level = borrow_mut_leaf_by_index(all_open_orders, tick_index);
            let mut order_id = *option::borrow(linked_table::front(&tick_level.open_orders));

            while (!linked_table::is_empty(&tick_level.open_orders)) {
                let maker_order = linked_table::borrow(&tick_level.open_orders, order_id);
                let mut maker_base_quantity = maker_order.quantity;
                let mut skip_order = false;

                if (maker_order.expire_timestamp <= current_timestamp) {
                    skip_order = true;
                    custodian::unlock_balance(&mut pool.base_custodian, maker_order.owner, maker_order.quantity);
                    emit_order_canceled<BaseAsset, QuoteAsset>(pool_id, maker_order);
                } else {
                    // Calculate how much quote asset (maker_quote_quantity) is required, including the commission, to fill the maker order.
                    let maker_quote_quantity_without_commission = clob_math::mul(
                        maker_base_quantity,
                        maker_order.price
                    );
                    let (is_round_down, mut taker_commission)  = clob_math::unsafe_mul_round(
                        maker_quote_quantity_without_commission,
                        pool.taker_fee_rate
                    );
                    if (is_round_down)  taker_commission = taker_commission + 1;

                    let maker_quote_quantity = maker_quote_quantity_without_commission + taker_commission;

                    // Total base quantity filled.
                    let mut filled_base_quantity: u64;
                    // Total quote quantity filled, excluding commission and rebate.
                    let mut filled_quote_quantity: u64;
                    // Total quote quantity paid by taker.
                    // filled_quote_quantity_without_commission * (FLOAT_SCALING + taker_fee_rate) = filled_quote_quantity
                    let mut filled_quote_quantity_without_commission: u64;
                    if (taker_quote_quantity_remaining > maker_quote_quantity) {
                        filled_quote_quantity = maker_quote_quantity;
                        filled_quote_quantity_without_commission = maker_quote_quantity_without_commission;
                        filled_base_quantity = maker_base_quantity;
                    } else {
                        terminate_loop = true;
                        // if not enough quote quantity to pay for taker commission, then no quantity will be filled
                        filled_quote_quantity_without_commission = clob_math::unsafe_div(
                            taker_quote_quantity_remaining,
                            FLOAT_SCALING + pool.taker_fee_rate
                        );
                        // filled_base_quantity = 0 is permitted since filled_quote_quantity_without_commission can be 0
                        filled_base_quantity = clob_math::unsafe_div(
                            filled_quote_quantity_without_commission,
                            maker_order.price
                        );
                        let filled_base_lot = filled_base_quantity / pool.lot_size;
                        filled_base_quantity = filled_base_lot * pool.lot_size;
                        // filled_quote_quantity_without_commission = 0 is permitted here since filled_base_quantity could be 0
                        filled_quote_quantity_without_commission = clob_math::unsafe_mul(
                            filled_base_quantity,
                            maker_order.price
                        );
                        // if taker_commission = 0 due to underflow, round it up to 1
                        let (round_down, mut taker_commission) = clob_math::unsafe_mul_round(
                            filled_quote_quantity_without_commission,
                            pool.taker_fee_rate
                        );
                        if (round_down) {
                            taker_commission = taker_commission + 1;
                        };
                        filled_quote_quantity = filled_quote_quantity_without_commission + taker_commission;
                    };
                    // if maker_rebate = 0 due to underflow, maker will not receive a rebate
                    let maker_rebate = clob_math::unsafe_mul(
                        filled_quote_quantity_without_commission,
                        pool.maker_rebate_rate
                    );
                    maker_base_quantity = maker_base_quantity - filled_base_quantity;

                    // maker in ask side, decrease maker's locked base asset, increase maker's available quote asset
                    taker_quote_quantity_remaining = taker_quote_quantity_remaining - filled_quote_quantity;
                    let locked_base_balance = custodian::decrease_user_locked_balance<BaseAsset>(
                        &mut pool.base_custodian,
                        maker_order.owner,
                        filled_base_quantity
                    );

                    let mut quote_balance_filled = balance::split(
                        &mut quote_balance_left,
                        filled_quote_quantity,
                    );
                    // Send quote asset including rebate to maker.
                    custodian::increase_user_available_balance<QuoteAsset>(
                        &mut pool.quote_custodian,
                        maker_order.owner,
                        balance::split(
                            &mut quote_balance_filled,
                            maker_rebate + filled_quote_quantity_without_commission,
                        ),
                    );
                    // Send remaining of commission - rebate to the protocol.
                    // commission - rebate = filled_quote_quantity_without_commission - filled_quote_quantity - maker_rebate
                    balance::join(&mut pool.quote_asset_trading_fees, quote_balance_filled);
                    balance::join(&mut base_balance_filled, locked_base_balance);

                    emit_order_filled<BaseAsset, QuoteAsset>(
                        *object::uid_as_inner(&pool.id),
                        maker_order,
                        filled_base_quantity,
                        // taker_commission = filled_quote_quantity - filled_quote_quantity_without_commission
                        // This guarantees that the subtraction will not underflow
                        filled_quote_quantity - filled_quote_quantity_without_commission,
                        maker_rebate
                    )
                };

                if (skip_order || maker_base_quantity == 0) {
                    // Remove the maker order.
                    let old_order_id = order_id;
                    let maybe_order_id = linked_table::next(&tick_level.open_orders, order_id);
                    if (!option::is_none(maybe_order_id)) {
                        order_id = *option::borrow(maybe_order_id);
                    };
                    let usr_open_order_ids = table::borrow_mut(&mut pool.usr_open_orders, maker_order.owner);
                    linked_table::remove(usr_open_order_ids, old_order_id);
                    linked_table::remove(&mut tick_level.open_orders, old_order_id);
                } else {
                    // Update the maker order.
                    let maker_order_mut = linked_table::borrow_mut(
                        &mut tick_level.open_orders,
                        order_id);
                    maker_order_mut.quantity = maker_base_quantity;
                };
                if (terminate_loop) {
                    break
                };
            };
            if (linked_table::is_empty(&tick_level.open_orders)) {
                (tick_price, _) = next_leaf(all_open_orders, tick_price);
                destroy_empty_level(remove_leaf_by_index(all_open_orders, tick_index));
                (_, tick_index) = find_leaf(all_open_orders, tick_price);
            };
            if (terminate_loop) {
                break
            };
        };
        return (base_balance_filled, quote_balance_left)
    }

    fun match_bid<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        quantity: u64,
        price_limit: u64,
        current_timestamp: u64,
        quote_balance: Balance<QuoteAsset>,
    ): (Balance<BaseAsset>, Balance<QuoteAsset>) {
        let pool_id = *object::uid_as_inner(&pool.id);
        // Base balance received by taker.
        // Need to individually keep track of the remaining base quantity to be filled to avoid infinite loop.
        let mut taker_base_quantity_remaining = quantity;
        let mut base_balance_filled = balance::zero<BaseAsset>();
        let mut quote_balance_left = quote_balance;
        let all_open_orders = &mut pool.asks;
        if (critbit::is_empty(all_open_orders)) {
            return (base_balance_filled, quote_balance_left)
        };
        let (mut tick_price, mut tick_index) = min_leaf(all_open_orders);

        while (!is_empty<TickLevel>(all_open_orders) && tick_price <= price_limit) {
            let tick_level = borrow_mut_leaf_by_index(all_open_orders, tick_index);
            let mut order_id = *option::borrow(linked_table::front(&tick_level.open_orders));

            while (!linked_table::is_empty(&tick_level.open_orders)) {
                let maker_order = linked_table::borrow(&tick_level.open_orders, order_id);
                let mut maker_base_quantity = maker_order.quantity;
                let mut skip_order = false;

                if (maker_order.expire_timestamp <= current_timestamp) {
                    skip_order = true;
                    custodian::unlock_balance(&mut pool.base_custodian, maker_order.owner, maker_order.quantity);
                    emit_order_canceled<BaseAsset, QuoteAsset>(pool_id, maker_order);
                } else {
                    let filled_base_quantity =
                        if (taker_base_quantity_remaining > maker_base_quantity) { maker_base_quantity }
                        else { taker_base_quantity_remaining };

                    let filled_quote_quantity = clob_math::mul(filled_base_quantity, maker_order.price);

                    // if maker_rebate = 0 due to underflow, maker will not receive a rebate
                    let maker_rebate = clob_math::unsafe_mul(filled_quote_quantity, pool.maker_rebate_rate);
                    // if taker_commission = 0 due to underflow, round it up to 1
                    let (is_round_down, mut taker_commission) = clob_math::unsafe_mul_round(
                        filled_quote_quantity,
                        pool.taker_fee_rate
                    );
                    if (is_round_down) taker_commission = taker_commission + 1;

                    maker_base_quantity = maker_base_quantity - filled_base_quantity;

                    // maker in ask side, decrease maker's locked base asset, increase maker's available quote asset
                    taker_base_quantity_remaining = taker_base_quantity_remaining - filled_base_quantity;
                    let locked_base_balance = custodian::decrease_user_locked_balance<BaseAsset>(
                        &mut pool.base_custodian,
                        maker_order.owner,
                        filled_base_quantity
                    );
                    let mut taker_commission_balance = balance::split(
                        &mut quote_balance_left,
                        taker_commission,
                    );
                    custodian::increase_user_available_balance<QuoteAsset>(
                        &mut pool.quote_custodian,
                        maker_order.owner,
                        balance::split(
                            &mut taker_commission_balance,
                            maker_rebate,
                        ),
                    );
                    balance::join(&mut pool.quote_asset_trading_fees, taker_commission_balance);
                    balance::join(&mut base_balance_filled, locked_base_balance);

                    custodian::increase_user_available_balance<QuoteAsset>(
                        &mut pool.quote_custodian,
                        maker_order.owner,
                        balance::split(
                            &mut quote_balance_left,
                            filled_quote_quantity,
                        ),
                    );

                    emit_order_filled<BaseAsset, QuoteAsset>(
                        *object::uid_as_inner(&pool.id),
                        maker_order,
                        filled_base_quantity,
                        taker_commission,
                        maker_rebate
                    );
                };

                if (skip_order || maker_base_quantity == 0) {
                    // Remove the maker order.
                    let old_order_id = order_id;
                    let maybe_order_id = linked_table::next(&tick_level.open_orders, order_id);
                    if (!option::is_none(maybe_order_id)) {
                        order_id = *option::borrow(maybe_order_id);
                    };
                    let usr_open_order_ids = table::borrow_mut(&mut pool.usr_open_orders, maker_order.owner);
                    linked_table::remove(usr_open_order_ids, old_order_id);
                    linked_table::remove(&mut tick_level.open_orders, old_order_id);
                } else {
                    // Update the maker order.
                    let maker_order_mut = linked_table::borrow_mut(
                        &mut tick_level.open_orders,
                        order_id);
                    maker_order_mut.quantity = maker_base_quantity;
                };
                if (taker_base_quantity_remaining == 0) {
                    break
                };
            };
            if (linked_table::is_empty(&tick_level.open_orders)) {
                (tick_price, _) = next_leaf(all_open_orders, tick_price);
                destroy_empty_level(remove_leaf_by_index(all_open_orders, tick_index));
                (_, tick_index) = find_leaf(all_open_orders, tick_price);
            };
            if (taker_base_quantity_remaining == 0) {
                break
            };
        };
        return (base_balance_filled, quote_balance_left)
    }

    fun match_ask<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        price_limit: u64,
        current_timestamp: u64,
        base_balance: Balance<BaseAsset>,
    ): (Balance<BaseAsset>, Balance<QuoteAsset>) {
        let pool_id = *object::uid_as_inner(&pool.id);
        let mut base_balance_left = base_balance;
        // Base balance received by taker, taking into account of taker commission.
        let mut quote_balance_filled = balance::zero<QuoteAsset>();
        let all_open_orders = &mut pool.bids;
        if (critbit::is_empty(all_open_orders)) {
            return (base_balance_left, quote_balance_filled)
        };
        let (mut tick_price, mut tick_index) = max_leaf(all_open_orders);
        while (!is_empty<TickLevel>(all_open_orders) && tick_price >= price_limit) {
            let tick_level = borrow_mut_leaf_by_index(all_open_orders, tick_index);
            let mut order_id = *option::borrow(linked_table::front(&tick_level.open_orders));
            while (!linked_table::is_empty(&tick_level.open_orders)) {
                let maker_order = linked_table::borrow(&tick_level.open_orders, order_id);
                let mut maker_base_quantity = maker_order.quantity;
                let mut skip_order = false;

                if (maker_order.expire_timestamp <= current_timestamp) {
                    skip_order = true;
                    let maker_quote_quantity = clob_math::mul(maker_order.quantity, maker_order.price);
                    custodian::unlock_balance(&mut pool.quote_custodian, maker_order.owner, maker_quote_quantity);
                    emit_order_canceled<BaseAsset, QuoteAsset>(pool_id, maker_order);
                } else {
                    let taker_base_quantity_remaining = balance::value(&base_balance_left);
                    let filled_base_quantity =
                        if (taker_base_quantity_remaining >= maker_base_quantity) { maker_base_quantity }
                        else { taker_base_quantity_remaining };

                    let filled_quote_quantity = clob_math::mul(filled_base_quantity, maker_order.price);

                    // if maker_rebate = 0 due to underflow, maker will not receive a rebate
                    let maker_rebate = clob_math::unsafe_mul(filled_quote_quantity, pool.maker_rebate_rate);
                    // if taker_commission = 0 due to underflow, round it up to 1
                    let (is_round_down, mut taker_commission) = clob_math::unsafe_mul_round(
                        filled_quote_quantity,
                        pool.taker_fee_rate
                    );
                    if (is_round_down) taker_commission = taker_commission + 1;

                    maker_base_quantity = maker_base_quantity - filled_base_quantity;
                    // maker in bid side, decrease maker's locked quote asset, increase maker's available base asset
                    let mut locked_quote_balance = custodian::decrease_user_locked_balance<QuoteAsset>(
                        &mut pool.quote_custodian,
                        maker_order.owner,
                        filled_quote_quantity
                    );
                    let mut taker_commission_balance = balance::split(
                        &mut locked_quote_balance,
                        taker_commission,
                    );
                    custodian::increase_user_available_balance<QuoteAsset>(
                        &mut pool.quote_custodian,
                        maker_order.owner,
                        balance::split(
                            &mut taker_commission_balance,
                            maker_rebate,
                        ),
                    );
                    balance::join(&mut pool.quote_asset_trading_fees, taker_commission_balance);
                    balance::join(&mut quote_balance_filled, locked_quote_balance);

                    custodian::increase_user_available_balance<BaseAsset>(
                        &mut pool.base_custodian,
                        maker_order.owner,
                        balance::split(
                            &mut base_balance_left,
                            filled_base_quantity,
                        ),
                    );

                    emit_order_filled<BaseAsset, QuoteAsset>(
                        *object::uid_as_inner(&pool.id),
                        maker_order,
                        filled_base_quantity,
                        taker_commission,
                        maker_rebate
                    );
                };

                if (skip_order || maker_base_quantity == 0) {
                    // Remove the maker order.
                    let old_order_id = order_id;
                    let maybe_order_id = linked_table::next(&tick_level.open_orders, order_id);
                    if (!option::is_none(maybe_order_id)) {
                        order_id = *option::borrow(maybe_order_id);
                    };
                    let usr_open_order_ids = table::borrow_mut(&mut pool.usr_open_orders, maker_order.owner);
                    linked_table::remove(usr_open_order_ids, old_order_id);
                    linked_table::remove(&mut tick_level.open_orders, old_order_id);
                } else {
                    // Update the maker order.
                    let maker_order_mut = linked_table::borrow_mut(
                        &mut tick_level.open_orders,
                        order_id);
                    maker_order_mut.quantity = maker_base_quantity;
                };
                if (balance::value(&base_balance_left) == 0) {
                    break
                };
            };
            if (linked_table::is_empty(&tick_level.open_orders)) {
                (tick_price, _) = previous_leaf(all_open_orders, tick_price);
                destroy_empty_level(remove_leaf_by_index(all_open_orders, tick_index));
                (_, tick_index) = find_leaf(all_open_orders, tick_price);
            };
            if (balance::value(&base_balance_left) == 0) {
                break
            };
        };
        return (base_balance_left, quote_balance_filled)
    }

    /// Place a market order to the order book.
    public fun place_market_order<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        quantity: u64,
        is_bid: bool,
        mut base_coin: Coin<BaseAsset>,
        mut quote_coin: Coin<QuoteAsset>,
        clock: &Clock,
        ctx: &mut TxContext,
    ): (Coin<BaseAsset>, Coin<QuoteAsset>) {
        // If market bid order, match against the open ask orders. Otherwise, match against the open bid orders.
        // Take market bid order for example.
        // We first retrieve the PriceLevel with the lowest price by calling min_leaf on the asks Critbit Tree.
        // We then match the market order by iterating through open orders on that price level in ascending order of the order id.
        // Open orders that are being filled are removed from the order book.
        // We stop the iteration untill all quantities are filled.
        // If the total quantity of open orders at the lowest price level is not large enough to fully fill the market order,
        // we move on to the next price level by calling next_leaf on the asks Critbit Tree and repeat the same procedure.
        // Continue iterating over the price levels in ascending order until the market order is completely filled.
        // If ther market order cannot be completely filled even after consuming all the open ask orders,
        // the unfilled quantity will be cancelled.
        // Market ask order follows similar procedure.
        // The difference is that market ask order is matched against the open bid orders.
        // We start with the bid PriceLeve with the highest price by calling max_leaf on the bids Critbit Tree.
        // The inner loop for iterating over the open orders in ascending orders of order id is the same as above.
        // Then iterate over the price levels in descending order until the market order is completely filled.
        assert!(quantity % pool.lot_size == 0, EInvalidQuantity);
        assert!(quantity != 0, EInvalidQuantity);
        if (is_bid) {
            let (base_balance_filled, quote_balance_left) = match_bid(
                pool,
                quantity,
                MAX_PRICE,
                clock::timestamp_ms(clock),
                coin::into_balance(quote_coin),
            );
            join(
                &mut base_coin,
                coin::from_balance(base_balance_filled, ctx),
            );
            quote_coin = coin::from_balance(quote_balance_left, ctx);
        } else {
            assert!(quantity <= coin::value(&base_coin), EInsufficientBaseCoin);
            let (base_balance_left, quote_balance_filled) = match_ask(
                pool,
                MIN_PRICE,
                clock::timestamp_ms(clock),
                coin::into_balance(base_coin),
            );
            base_coin = coin::from_balance(base_balance_left, ctx);
            join(
                &mut quote_coin,
                coin::from_balance(quote_balance_filled, ctx),
            );
        };
        (base_coin, quote_coin)
    }

    /// Injects a maker order to the order book.
    /// Returns the order id.
    fun inject_limit_order<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        price: u64,
        quantity: u64,
        is_bid: bool,
        expire_timestamp: u64,
        account_cap: &AccountCap,
        ctx: &mut TxContext
    ): u64 {
        let user = object::id(account_cap);
        let order_id: u64;
        let open_orders: &mut CritbitTree<TickLevel>;
        if (is_bid) {
            let quote_quantity = clob_math::mul(quantity, price);
            custodian::lock_balance<QuoteAsset>(&mut pool.quote_custodian, account_cap, quote_quantity);
            order_id = pool.next_bid_order_id;
            pool.next_bid_order_id = pool.next_bid_order_id + 1;
            open_orders = &mut pool.bids;
        } else {
            custodian::lock_balance<BaseAsset>(&mut pool.base_custodian, account_cap, quantity);
            order_id = pool.next_ask_order_id;
            pool.next_ask_order_id = pool.next_ask_order_id + 1;
            open_orders = &mut pool.asks;
        };
        let order = Order {
            order_id,
            price,
            quantity,
            is_bid,
            owner: user,
            expire_timestamp,
        };
        let (tick_exists, mut tick_index) = find_leaf(open_orders, price);
        if (!tick_exists) {
            tick_index = insert_leaf(
                open_orders,
                price,
                TickLevel {
                    price,
                    open_orders: linked_table::new(ctx),
                });
        };

        let tick_level = borrow_mut_leaf_by_index(open_orders, tick_index);
        linked_table::push_back(&mut tick_level.open_orders, order_id, order);
        event::emit(OrderPlacedV2<BaseAsset, QuoteAsset> {
            pool_id: *object::uid_as_inner(&pool.id),
            order_id,
            is_bid,
            owner: user,
            base_asset_quantity_placed: quantity,
            price,
            expire_timestamp
        });
        if (!contains(&pool.usr_open_orders, user)) {
            add(&mut pool.usr_open_orders, user, linked_table::new(ctx));
        };
        linked_table::push_back(borrow_mut(&mut pool.usr_open_orders, user), order_id, price);

        return order_id
    }

    /// Place a limit order to the order book.
    /// Returns (base quantity filled, quote quantity filled, whether a maker order is being placed, order id of the maker order).
    /// When the limit order is not successfully placed, we return false to indicate that and also returns a meaningless order_id 0.
    /// When the limit order is successfully placed, we return true to indicate that and also the corresponding order_id.
    /// So please check that boolean value first before using the order id.
    public fun place_limit_order<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        price: u64,
        quantity: u64,
        is_bid: bool,
        expire_timestamp: u64, // Expiration timestamp in ms in absolute value inclusive.
        restriction: u8,
        clock: &Clock,
        account_cap: &AccountCap,
        ctx: &mut TxContext
    ): (u64, u64, bool, u64) {
        // If limit bid order, check whether the price is lower than the lowest ask order by checking the min_leaf of asks Critbit Tree.
        // If so, assign the sequence id of the order to be next_bid_order_id and increment next_bid_order_id by 1.
        // Inject the new order to the bids Critbit Tree according to the price and order id.
        // Otherwise, find the price level from the asks Critbit Tree that is no greater than the input price.
        // Match the bid order against the asks Critbit Tree in the same way as a market order but up until the price level found in the previous step.
        // If the bid order is not completely filled, inject the remaining quantity to the bids Critbit Tree according to the input price and order id.
        // If limit ask order, vice versa.
        assert!(quantity > 0, EInvalidQuantity);
        assert!(price > 0, EInvalidPrice);
        assert!(price % pool.tick_size == 0, EInvalidPrice);
        assert!(quantity % pool.lot_size == 0, EInvalidQuantity);
        assert!(expire_timestamp > clock::timestamp_ms(clock), EInvalidExpireTimestamp);
        let user = object::id(account_cap);
        let base_quantity_filled;
        let quote_quantity_filled;

        if (is_bid) {
            let quote_quantity_original = custodian::account_available_balance<QuoteAsset>(
                &pool.quote_custodian,
                user,
            );
            let quote_balance = custodian::decrease_user_available_balance<QuoteAsset>(
                &mut pool.quote_custodian,
                account_cap,
                quote_quantity_original,
            );
            let (base_balance_filled, quote_balance_left) = match_bid(
                pool,
                quantity,
                price,
                clock::timestamp_ms(clock),
                quote_balance,
            );
            base_quantity_filled = balance::value(&base_balance_filled);
            quote_quantity_filled = quote_quantity_original - balance::value(&quote_balance_left);

            custodian::increase_user_available_balance<BaseAsset>(
                &mut pool.base_custodian,
                user,
                base_balance_filled,
            );
            custodian::increase_user_available_balance<QuoteAsset>(
                &mut pool.quote_custodian,
                user,
                quote_balance_left,
            );
        } else {
            let base_balance = custodian::decrease_user_available_balance<BaseAsset>(
                &mut pool.base_custodian,
                account_cap,
                quantity,
            );
            let (base_balance_left, quote_balance_filled) = match_ask(
                pool,
                price,
                clock::timestamp_ms(clock),
                base_balance,
            );

            base_quantity_filled = quantity - balance::value(&base_balance_left);
            quote_quantity_filled = balance::value(&quote_balance_filled);

            custodian::increase_user_available_balance<BaseAsset>(
                &mut pool.base_custodian,
                user,
                base_balance_left,
            );
            custodian::increase_user_available_balance<QuoteAsset>(
                &mut pool.quote_custodian,
                user,
                quote_balance_filled,
            );
        };

        let order_id;
        if (restriction == IMMEDIATE_OR_CANCEL) {
            return (base_quantity_filled, quote_quantity_filled, false, 0)
        };
        if (restriction == FILL_OR_KILL) {
            assert!(base_quantity_filled == quantity, EOrderCannotBeFullyFilled);
            return (base_quantity_filled, quote_quantity_filled, false, 0)
        };
        if (restriction == POST_OR_ABORT) {
            assert!(base_quantity_filled == 0, EOrderCannotBeFullyPassive);
            order_id = inject_limit_order(pool, price, quantity, is_bid, expire_timestamp, account_cap, ctx);
            return (base_quantity_filled, quote_quantity_filled, true, order_id)
        } else {
            assert!(restriction == NO_RESTRICTION, EInvalidRestriction);
            if (quantity > base_quantity_filled) {
                order_id = inject_limit_order(
                    pool,
                    price,
                    quantity - base_quantity_filled,
                    is_bid,
                    expire_timestamp,
                    account_cap,
                    ctx
                );
                return (base_quantity_filled, quote_quantity_filled, true, order_id)
            };
            return (base_quantity_filled, quote_quantity_filled, false, 0)
        }
    }

    fun order_is_bid(order_id: u64): bool {
        return order_id < MIN_ASK_ORDER_ID
    }

    fun emit_order_canceled<BaseAsset, QuoteAsset>(
        pool_id: ID,
        order: &Order
    ) {
        event::emit(OrderCanceled<BaseAsset, QuoteAsset> {
            pool_id,
            order_id: order.order_id,
            is_bid: order.is_bid,
            owner: order.owner,
            base_asset_quantity_canceled: order.quantity,
            price: order.price
        })
    }

    fun emit_order_filled<BaseAsset, QuoteAsset>(
        pool_id: ID,
        order: &Order,
        base_asset_quantity_filled: u64,
        taker_commission: u64,
        maker_rebates: u64
    ) {
        event::emit(OrderFilledV2<BaseAsset, QuoteAsset> {
            pool_id,
            order_id: order.order_id,
            is_bid: order.is_bid,
            owner: order.owner,
            total_quantity: order.quantity,
            base_asset_quantity_filled,
            // order.quantity = base_asset_quantity_filled + base_asset_quantity_remaining
            // This guarantees that the subtraction will not underflow
            base_asset_quantity_remaining: order.quantity - base_asset_quantity_filled,
            price: order.price,
            taker_commission,
            maker_rebates
        })
    }

    /// Cancel and opening order.
    /// Abort if order_id is invalid or if the order is not submitted by the transaction sender.
    public fun cancel_order<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        order_id: u64,
        account_cap: &AccountCap
    ) {
        // First check the highest bit of the order id to see whether it's bid or ask.
        // Then retrieve the price using the order id.
        // Using the price to retrieve the corresponding PriceLevel from the bids / asks Critbit Tree.
        // Retrieve and remove the order from open orders of the PriceLevel.
        let user = object::id(account_cap);
        assert!(contains(&pool.usr_open_orders, user), EInvalidUser);
        let usr_open_orders = borrow_mut(&mut pool.usr_open_orders, user);
        assert!(linked_table::contains(usr_open_orders, order_id), EInvalidOrderId);
        let tick_price = *linked_table::borrow(usr_open_orders, order_id);
        let is_bid = order_is_bid(order_id);
        let (tick_exists, tick_index) = find_leaf(
            if (is_bid) { &pool.bids } else { &pool.asks },
            tick_price);
        assert!(tick_exists, EInvalidOrderId);
        let order = remove_order(
            if (is_bid) { &mut pool.bids } else { &mut pool.asks },
            usr_open_orders,
            tick_index,
            order_id,
            user
        );
        if (is_bid) {
            let balance_locked = clob_math::mul(order.quantity, order.price);
            custodian::unlock_balance(&mut pool.quote_custodian, user, balance_locked);
        } else {
            custodian::unlock_balance(&mut pool.base_custodian, user, order.quantity);
        };
        emit_order_canceled<BaseAsset, QuoteAsset>(*object::uid_as_inner(&pool.id), &order);
    }

    fun remove_order(
        open_orders: &mut CritbitTree<TickLevel>,
        usr_open_orders: &mut LinkedTable<u64, u64>,
        tick_index: u64,
        order_id: u64,
        user: ID,
    ): Order {
        linked_table::remove(usr_open_orders, order_id);
        let tick_level = borrow_leaf_by_index(open_orders, tick_index);
        assert!(linked_table::contains(&tick_level.open_orders, order_id), EInvalidOrderId);
        let mut_tick_level = borrow_mut_leaf_by_index(open_orders, tick_index);
        let order = linked_table::remove(&mut mut_tick_level.open_orders, order_id);
        assert!(order.owner == user, EUnauthorizedCancel);
        if (linked_table::is_empty(&mut_tick_level.open_orders)) {
            destroy_empty_level(remove_leaf_by_index(open_orders, tick_index));
        };
        order
    }

    public fun cancel_all_orders<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        account_cap: &AccountCap
    ) {
        let pool_id = *object::uid_as_inner(&pool.id);
        let user = object::id(account_cap);
        assert!(contains(&pool.usr_open_orders, user), EInvalidUser);
        let usr_open_order_ids = table::borrow_mut(&mut pool.usr_open_orders, user);
        while (!linked_table::is_empty(usr_open_order_ids)) {
            let order_id = *option::borrow(linked_table::back(usr_open_order_ids));
            let order_price = *linked_table::borrow(usr_open_order_ids, order_id);
            let is_bid = order_is_bid(order_id);
            let open_orders =
                if (is_bid) { &mut pool.bids }
                else { &mut pool.asks };
            let (_, tick_index) = critbit::find_leaf(open_orders, order_price);
            let order = remove_order(
                open_orders,
                usr_open_order_ids,
                tick_index,
                order_id,
                user
            );
            if (is_bid) {
                let balance_locked = clob_math::mul(order.quantity, order.price);
                custodian::unlock_balance(&mut pool.quote_custodian, user, balance_locked);
            } else {
                custodian::unlock_balance(&mut pool.base_custodian, user, order.quantity);
            };
            emit_order_canceled<BaseAsset, QuoteAsset>(pool_id, &order);
        };
    }


    /// Batch cancel limit orders to save gas cost.
    /// Abort if any of the order_ids are not submitted by the sender.
    /// Skip any order_id that is invalid.
    /// Note that this function can reduce gas cost even further if caller has multiple orders at the same price level,
    /// and if orders with the same price are grouped together in the vector.
    /// For example, if we have the following order_id to price mapping, {0: 100., 1: 200., 2: 100., 3: 200.}.
    /// Grouping order_ids like [0, 2, 1, 3] would make it the most gas efficient.
    public fun batch_cancel_order<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        order_ids: vector<u64>,
        account_cap: &AccountCap
    ) {
        let pool_id = *object::uid_as_inner(&pool.id);
        // First group the order ids according to price level,
        // so that we don't have to retrieve the PriceLevel multiple times if there are orders at the same price level.
        // Iterate over each price level, retrieve the corresponding PriceLevel.
        // Iterate over the order ids that need to be canceled at that price level,
        // retrieve and remove the order from open orders of the PriceLevel.
        let user = object::id(account_cap);
        assert!(contains(&pool.usr_open_orders, user), 0);
        let mut tick_index: u64 = 0;
        let mut tick_price: u64 = 0;
        let n_order = vector::length(&order_ids);
        let mut i_order = 0;
        let usr_open_orders = borrow_mut(&mut pool.usr_open_orders, user);
        while (i_order < n_order) {
            let order_id = *vector::borrow(&order_ids, i_order);
            assert!(linked_table::contains(usr_open_orders, order_id), EInvalidOrderId);
            let new_tick_price = *linked_table::borrow(usr_open_orders, order_id);
            let is_bid = order_is_bid(order_id);
            if (new_tick_price != tick_price) {
                tick_price = new_tick_price;
                let (tick_exists, new_tick_index) = find_leaf(
                    if (is_bid) { &pool.bids } else { &pool.asks },
                    tick_price
                );
                assert!(tick_exists, EInvalidTickPrice);
                tick_index = new_tick_index;
            };
            let order = remove_order(
                if (is_bid) { &mut pool.bids } else { &mut pool.asks },
                usr_open_orders,
                tick_index,
                order_id,
                user
            );
            if (is_bid) {
                let balance_locked = clob_math::mul(order.quantity, order.price);
                custodian::unlock_balance(&mut pool.quote_custodian, user, balance_locked);
            } else {
                custodian::unlock_balance(&mut pool.base_custodian, user, order.quantity);
            };
            emit_order_canceled<BaseAsset, QuoteAsset>(pool_id, &order);
            i_order = i_order + 1;
        }
    }

    public fun list_open_orders<BaseAsset, QuoteAsset>(
        pool: &Pool<BaseAsset, QuoteAsset>,
        account_cap: &AccountCap
    ): vector<Order> {
        let user = object::id(account_cap);
        let usr_open_order_ids = table::borrow(&pool.usr_open_orders, user);
        let mut open_orders = vector::empty<Order>();
        let mut order_id = linked_table::front(usr_open_order_ids);
        while (!option::is_none(order_id)) {
            let order_price = *linked_table::borrow(usr_open_order_ids, *option::borrow(order_id));
            let tick_level =
                if (order_is_bid(*option::borrow(order_id))) borrow_leaf_by_key(&pool.bids, order_price)
                else borrow_leaf_by_key(&pool.asks, order_price);
            let order = linked_table::borrow(&tick_level.open_orders, *option::borrow(order_id));
            vector::push_back(&mut open_orders, Order {
                order_id: order.order_id,
                price: order.price,
                quantity: order.quantity,
                is_bid: order.is_bid,
                owner: order.owner,
                expire_timestamp: order.expire_timestamp
            });
            order_id = linked_table::next(usr_open_order_ids, *option::borrow(order_id));
        };
        open_orders
    }

    /// query user balance inside custodian
    public fun account_balance<BaseAsset, QuoteAsset>(
        pool: &Pool<BaseAsset, QuoteAsset>,
        account_cap: &AccountCap
    ): (u64, u64, u64, u64) {
        let user = object::id(account_cap);
        let (base_avail, base_locked) = custodian::account_balance(&pool.base_custodian, user);
        let (quote_avail, quote_locked) = custodian::account_balance(&pool.quote_custodian, user);
        (base_avail, base_locked, quote_avail, quote_locked)
    }

    /// Query the market price of order book
    /// returns (best_bid_price, best_ask_price)
    public fun get_market_price<BaseAsset, QuoteAsset>(
        pool: &Pool<BaseAsset, QuoteAsset>
    ): (u64, u64){
        let (bid_price, _) = critbit::max_leaf(&pool.bids);
        let (ask_price, _) = critbit::min_leaf(&pool.asks);
        return (bid_price, ask_price)
    }

    /// Enter a price range and return the level2 order depth of all valid prices within this price range in bid side
    /// returns two vectors of u64
    /// The previous is a list of all valid prices
    /// The latter is the corresponding depth list
    public fun get_level2_book_status_bid_side<BaseAsset, QuoteAsset>(
        pool: &Pool<BaseAsset, QuoteAsset>,
        mut price_low: u64,
        mut price_high: u64,
        clock: &Clock
    ): (vector<u64>, vector<u64>) {
        let (price_low_, _) = critbit::min_leaf(&pool.bids);
        if (price_low < price_low_) price_low = price_low_;
        let (price_high_, _) = critbit::max_leaf(&pool.bids);
        if (price_high > price_high_) price_high = price_high_;
        price_low = critbit::find_closest_key(&pool.bids, price_low);
        price_high = critbit::find_closest_key(&pool.bids, price_high);
        let mut price_vec = vector::empty<u64>();
        let mut depth_vec = vector::empty<u64>();
        if (price_low == 0) { return (price_vec, depth_vec) };
        while (price_low <= price_high) {
            let depth = get_level2_book_status(
                &pool.bids,
                price_low,
                clock::timestamp_ms(clock)
            );
            vector::push_back(&mut price_vec, price_low);
            vector::push_back(&mut depth_vec, depth);
            let (next_price, _) = critbit::next_leaf(&pool.bids, price_low);
            if (next_price == 0) { break }
            else { price_low = next_price };
        };
        (price_vec, depth_vec)
    }

    /// Enter a price range and return the level2 order depth of all valid prices within this price range in ask side
    /// returns two vectors of u64
    /// The previous is a list of all valid prices
    /// The latter is the corresponding depth list
    public fun get_level2_book_status_ask_side<BaseAsset, QuoteAsset>(
        pool: &Pool<BaseAsset, QuoteAsset>,
        mut price_low: u64,
        mut price_high: u64,
        clock: &Clock
    ): (vector<u64>, vector<u64>) {
        let (price_low_, _) = critbit::min_leaf(&pool.asks);
        if (price_low < price_low_) price_low = price_low_;
        let (price_high_, _) = critbit::max_leaf(&pool.asks);
        if (price_high > price_high_) price_high = price_high_;
        price_low = critbit::find_closest_key(&pool.asks, price_low);
        price_high = critbit::find_closest_key(&pool.asks, price_high);
        let mut price_vec = vector::empty<u64>();
        let mut depth_vec = vector::empty<u64>();
        if (price_low == 0) { return (price_vec, depth_vec) };
        while (price_low <= price_high) {
            let depth = get_level2_book_status(
                &pool.asks,
                price_low,
                clock::timestamp_ms(clock)
            );
            vector::push_back(&mut price_vec, price_low);
            vector::push_back(&mut depth_vec, depth);
            let (next_price, _) = critbit::next_leaf(&pool.asks, price_low);
            if (next_price == 0) { break }
            else { price_low = next_price };
        };
        (price_vec, depth_vec)
    }

    /// internal func to retrive single depth of a tick price
    fun get_level2_book_status(
        open_orders: &CritbitTree<TickLevel>,
        price: u64,
        time_stamp: u64
    ): u64 {
        let tick_level = critbit::borrow_leaf_by_key(open_orders, price);
        let tick_open_orders = &tick_level.open_orders;
        let mut depth = 0;
        let mut order_id = linked_table::front(tick_open_orders);
        let mut order: &Order;
        while (!option::is_none(order_id)) {
            order = linked_table::borrow(tick_open_orders, *option::borrow(order_id));
            if (order.expire_timestamp > time_stamp) depth = depth + order.quantity;
            order_id = linked_table::next(tick_open_orders, *option::borrow(order_id));
        };
        depth
    }

    public fun get_order_status<BaseAsset, QuoteAsset>(
        pool: &Pool<BaseAsset, QuoteAsset>,
        order_id: u64,
        account_cap: &AccountCap
    ): &Order {
        let user = object::id(account_cap);
        assert!(table::contains(&pool.usr_open_orders, user), EInvalidUser);
        let usr_open_order_ids = table::borrow(&pool.usr_open_orders, user);
        assert!(linked_table::contains(usr_open_order_ids, order_id), EInvalidOrderId);
        let order_price = *linked_table::borrow(usr_open_order_ids, order_id);
        let open_orders =
            if (order_id < MIN_ASK_ORDER_ID) { &pool.bids }
            else { &pool.asks };
        let tick_level = critbit::borrow_leaf_by_key(open_orders, order_price);
        let tick_open_orders = &tick_level.open_orders;
        let order = linked_table::borrow(tick_open_orders, order_id);
        order
    }


    // Note that open orders and quotes can be directly accessed by loading in the entire Pool.

    #[test_only] use sui::test_scenario::{Self, Scenario};

    #[test_only] const E_NULL: u64 = 0;

    #[test_only] public struct USD {}

    #[test_only]
    public fun setup_test_with_tick_lot(
        taker_fee_rate: u64,
        maker_rebate_rate: u64,
        // tick size with scaling
        tick_size: u64,
        lot_size: u64,
        scenario: &mut Scenario,
        sender: address,
    ) {
        test_scenario::next_tx(scenario, sender);
        {
            clock::share_for_testing(clock::create_for_testing(test_scenario::ctx(scenario)));
        };

        test_scenario::next_tx(scenario, sender);
        {
            create_pool_<SUI, USD>(
                taker_fee_rate,
                maker_rebate_rate,
                tick_size,
                lot_size,
                balance::create_for_testing(FEE_AMOUNT_FOR_CREATE_POOL),
                test_scenario::ctx(scenario)
            );
        };
    }

    #[test_only]
    public fun setup_test(
        taker_fee_rate: u64,
        maker_rebate_rate: u64,
        scenario: &mut Scenario,
        sender: address,
    ) {
        setup_test_with_tick_lot(
            taker_fee_rate,
            maker_rebate_rate,
            1 * FLOAT_SCALING,
            1,
            scenario,
            sender,
        );
    }

    #[test_only]
    fun order_equal(
        order_left: &Order,
        order_right: &Order,
    ): bool {
        return (order_left.order_id == order_right.order_id) &&
            (order_left.price == order_right.price) &&
            (order_left.quantity == order_right.quantity) &&
            (order_left.is_bid == order_right.is_bid) &&
            (order_left.owner == order_right.owner)
    }

    #[test_only]
    fun contains_order(
        tree: &LinkedTable<u64, Order>,
        expected_order: &Order,
    ): bool {
        if (!linked_table::contains(tree, expected_order.order_id)) {
            return false
        };
        let order = linked_table::borrow(tree, expected_order.order_id);
        return order_equal(order, expected_order)
    }

    #[test_only]
    public fun check_tick_level(
        tree: &CritbitTree<TickLevel>,
        price: u64,
        open_orders: &vector<Order>,
    ) {
        let (tick_exists, tick_index) = find_leaf(tree, price);
        assert!(tick_exists, E_NULL);
        let tick_level = borrow_leaf_by_index(tree, tick_index);
        assert!(tick_level.price == price, E_NULL);
        let mut total_quote_amount: u64 = 0;
        assert!(linked_table::length(&tick_level.open_orders) == vector::length(open_orders), E_NULL);
        let mut i_order = 0;
        while (i_order < vector::length(open_orders)) {
            let order = vector::borrow(open_orders, i_order);
            total_quote_amount = total_quote_amount + order.quantity;
            assert!(order.price == price, E_NULL);
            assert!(contains_order(&tick_level.open_orders, order), E_NULL);
            i_order = i_order + 1;
        };
    }

    #[test_only]
    public fun check_empty_tick_level(
        tree: &CritbitTree<TickLevel>,
        price: u64,
    ) {
        let (tick_exists, _) = find_leaf(tree, price);
        assert!(!tick_exists, E_NULL);
    }


    #[test_only]
    public fun order_id(
        sequence_id: u64,
        is_bid: bool
    ): u64 {
        return if (is_bid) { MIN_BID_ORDER_ID + sequence_id } else { MIN_ASK_ORDER_ID + sequence_id }
    }

    #[test_only]
    public fun mint_account_cap_transfer(
        user: address,
        ctx: &mut TxContext
    ) {
        transfer::public_transfer(create_account(ctx), user);
    }

    #[test_only]
    public fun borrow_mut_custodian<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>
    ): (&mut Custodian<BaseAsset>, &mut Custodian<QuoteAsset>) {
        (&mut pool.base_custodian, &mut pool.quote_custodian)
    }

    #[test_only]
    public fun borrow_custodian<BaseAsset, QuoteAsset>(
        pool: & Pool<BaseAsset, QuoteAsset>
    ): (&Custodian<BaseAsset>, &Custodian<QuoteAsset>) {
        (&pool.base_custodian, &pool.quote_custodian)
    }

    #[test_only]
    public fun test_match_bid<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        quantity: u64,
        price_limit: u64, // upper price limit if bid, lower price limit if ask, inclusive
        current_timestamp: u64,
    ): (u64, u64) {
        let quote_quantity_original = 1 << 63;
        let (base_balance_filled, quote_balance_left) = match_bid(
            pool,
            quantity,
            price_limit,
            current_timestamp,
            balance::create_for_testing<QuoteAsset>(quote_quantity_original),
        );
        let base_quantity_filled = balance::value(&base_balance_filled);
        let quote_quantity_filled = quote_quantity_original - balance::value(&quote_balance_left);
        balance::destroy_for_testing(base_balance_filled);
        balance::destroy_for_testing(quote_balance_left);
        return (base_quantity_filled, quote_quantity_filled)
    }

    #[test_only]
    public fun test_match_bid_with_quote_quantity<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        quantity: u64,
        price_limit: u64, // upper price limit if bid, lower price limit if ask, inclusive
        current_timestamp: u64,
    ): (u64, u64) {
        let quote_quantity_original = 1 << 63;
        let (base_balance_filled, quote_balance_left) = match_bid_with_quote_quantity(
            pool,
            quantity,
            price_limit,
            current_timestamp,
            balance::create_for_testing<QuoteAsset>(quote_quantity_original),
        );
        let base_quantity_filled = balance::value(&base_balance_filled);
        let quote_quantity_filled = quote_quantity_original - balance::value(&quote_balance_left);
        balance::destroy_for_testing(base_balance_filled);
        balance::destroy_for_testing(quote_balance_left);
        return (base_quantity_filled, quote_quantity_filled)
    }

    #[test_only]
    public fun test_match_ask<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        quantity: u64,
        price_limit: u64, // upper price limit if bid, lower price limit if ask, inclusive
        current_timestamp: u64,
    ): (u64, u64) {
        let (base_balance_left, quote_balance_filled) = match_ask(
            pool,
            price_limit,
            current_timestamp,
            balance::create_for_testing<BaseAsset>(quantity),
        );
        let base_quantity_filled = quantity - balance::value(&base_balance_left);
        let quote_quantity_filled = balance::value(&quote_balance_filled);
        balance::destroy_for_testing(base_balance_left);
        balance::destroy_for_testing(quote_balance_filled);
        return (base_quantity_filled, quote_quantity_filled)
    }

    #[test_only]
    public fun test_inject_limit_order<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        price: u64,
        quantity: u64,
        is_bid: bool,
        account_cap: &AccountCap,
        ctx: &mut TxContext
    ) {
        inject_limit_order(pool, price, quantity, is_bid, TIMESTAMP_INF, account_cap, ctx);
    }

    #[test_only]
    public fun test_inject_limit_order_with_expiration<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        price: u64,
        quantity: u64,
        is_bid: bool,
        expire_timestamp: u64,
        account_cap: &AccountCap,
        ctx: &mut TxContext
    ) {
        inject_limit_order(pool, price, quantity, is_bid, expire_timestamp, account_cap, ctx);
    }

    #[test_only]
    public fun get_pool_stat<BaseAsset, QuoteAsset>(
        pool: &Pool<BaseAsset, QuoteAsset>
    ): (u64, u64, &CritbitTree<TickLevel>, &CritbitTree<TickLevel>) {
        (
            pool.next_bid_order_id,
            pool.next_ask_order_id,
            &pool.bids,
            &pool.asks
        )
    }

    #[test_only]
    public fun get_usr_open_orders<BaseAsset, QuoteAsset>(
        pool: &Pool<BaseAsset, QuoteAsset>,
        owner: ID
    ): &LinkedTable<u64, u64> {
        assert!(contains(&pool.usr_open_orders, owner), 0);
        table::borrow(&pool.usr_open_orders, owner)
    }

    #[test_only]
    public fun test_construct_order(sequence_id: u64, price: u64, quantity: u64, is_bid: bool, owner: ID): Order {
        Order {
            order_id: order_id(sequence_id, is_bid),
            price,
            quantity,
            is_bid,
            owner,
            expire_timestamp: TIMESTAMP_INF,
        }
    }

    #[test_only]
    public fun test_construct_order_with_expiration(
        sequence_id: u64,
        price: u64,
        quantity: u64,
        is_bid: bool,
        owner: ID,
        expire_timestamp: u64
    ): Order {
        Order {
            order_id: order_id(sequence_id, is_bid),
            price,
            quantity,
            is_bid,
            owner,
            expire_timestamp,
        }
    }

    #[test_only]
    public fun check_usr_open_orders(
        usr_open_orders: &LinkedTable<u64, u64>,
        usr_open_orders_cmp: &vector<u64>,
    ) {
        assert!(2 * linked_table::length(usr_open_orders) == vector::length(usr_open_orders_cmp), 0);
        let mut i_order = 0;
        while (i_order < vector::length(usr_open_orders_cmp)) {
            let order_id = *vector::borrow(usr_open_orders_cmp, i_order);
            i_order = i_order + 1;
            assert!(linked_table::contains(usr_open_orders, order_id), 0);
            let price_cmp = *vector::borrow(usr_open_orders_cmp, i_order);
            let price = *linked_table::borrow(usr_open_orders, order_id);
            assert!(price_cmp == price, ENotEqual);
            i_order = i_order + 1;
        };
    }

    #[test_only]
    public fun test_remove_order<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        tick_index: u64,
        sequence_id: u64,
        is_bid: bool,
        owner: ID,
    ): Order {
        let order;
        if (is_bid) {
            order = remove_order(
                &mut pool.bids,
                borrow_mut(&mut pool.usr_open_orders, owner),
                tick_index,
                order_id(sequence_id, is_bid),
                owner
            )
        } else {
            order = remove_order(
                &mut pool.asks,
                borrow_mut(&mut pool.usr_open_orders, owner),
                tick_index,
                order_id(sequence_id, is_bid),
                owner
            )
        };
        order
    }

    // === Deprecated ===
    #[allow(unused_field)]
    /// Deprecated since v1.0.0, use `OrderPlacedV2` instead.
    public struct OrderPlaced<phantom BaseAsset, phantom QuoteAsset> has copy, store, drop {
        /// object ID of the pool the order was placed on
        pool_id: ID,
        /// ID of the order within the pool
        order_id: u64,
        is_bid: bool,
        /// object ID of the `AccountCap` that placed the order
        owner: ID,
        base_asset_quantity_placed: u64,
        price: u64,
    }

    #[allow(unused_field)]
    /// Deprecated since v1.0.0, use `OrderFilledV2` instead.
    public struct OrderFilled<phantom BaseAsset, phantom QuoteAsset> has copy, store, drop {
        /// object ID of the pool the order was placed on
        pool_id: ID,
        /// ID of the order within the pool
        order_id: u64,
        is_bid: bool,
        /// object ID of the `AccountCap` that placed the order
        owner: ID,
        total_quantity: u64,
        base_asset_quantity_filled: u64,
        base_asset_quantity_remaining: u64,
        price: u64
    }

}
