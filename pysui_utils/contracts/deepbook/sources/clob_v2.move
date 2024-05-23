// Copyright (c) Mysten Labs, Inc.
// SPDX-License-Identifier: Apache-2.0

module deepbook::clob_v2 {
    use std::type_name::{Self, TypeName};

    use sui::balance::{Self, Balance};
    use sui::clock::{Self, Clock};
    use sui::coin::{Self, Coin, join};
    use sui::event;
    use sui::linked_table::{Self, LinkedTable};
    use sui::sui::SUI;
    use sui::table::{Self, Table, contains, add, borrow_mut};

    use deepbook::critbit::{Self, CritbitTree, is_empty, borrow_mut_leaf_by_index, min_leaf, remove_leaf_by_index, max_leaf, next_leaf, previous_leaf, borrow_leaf_by_index, borrow_leaf_by_key, find_leaf, insert_leaf};
    use deepbook::custodian_v2::{Self as custodian, Custodian, AccountCap, mint_account_cap, account_owner};
    use deepbook::math::Self as clob_math;

    // <<<<<<<<<<<<<<<<<<<<<<<< Error codes <<<<<<<<<<<<<<<<<<<<<<<<
    const EIncorrectPoolOwner: u64 = 1;
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
    const ENotEqual: u64 = 13;
    const EInvalidRestriction: u64 = 14;
    const EInvalidPair: u64 = 16;
    const EInvalidFee: u64 = 18;
    const EInvalidExpireTimestamp: u64 = 19;
    const EInvalidTickSizeMinSize: u64 = 20;
    const EInvalidSelfMatchingPreventionArg: u64 = 21;

    // <<<<<<<<<<<<<<<<<<<<<<<< Error codes <<<<<<<<<<<<<<<<<<<<<<<<

    // <<<<<<<<<<<<<<<<<<<<<<<< Constants <<<<<<<<<<<<<<<<<<<<<<<<
    const FLOAT_SCALING: u64 = 1_000_000_000;
    // Self-Trade Prevention option
    // Cancel older (resting) order in full. Continue to execute the newer taking order.
    const CANCEL_OLDEST: u8 = 0;
    // Restrictions on limit orders.
    const NO_RESTRICTION: u8 = 0;
    // Mandates that whatever amount of an order that can be executed in the current transaction, be filled and then the rest of the order canceled.
    const IMMEDIATE_OR_CANCEL: u8 = 1;
    // Mandates that the entire order size be filled in the current transaction. Otherwise, the order is canceled.
    const FILL_OR_KILL: u8 = 2;
    // Mandates that the entire order be passive. Otherwise, cancel the order.
    const POST_OR_ABORT: u8 = 3;
    const MIN_BID_ORDER_ID: u64 = 1;
    const MIN_ASK_ORDER_ID: u64 = 1 << 63;
    const MIN_PRICE: u64 = 0;
    const MAX_PRICE: u64 = (1u128 << 64 - 1) as u64;
    // Trade quantities must be in multiples of 1000. The lot_size in the pool structs is used as min_size.
    const LOT_SIZE: u64 = 1000;
    #[test_only]
    const TIMESTAMP_INF: u64 = (1u128 << 64 - 1) as u64;
    const REFERENCE_TAKER_FEE_RATE: u64 = 2_500_000;
    const REFERENCE_MAKER_REBATE_RATE: u64 = 1_500_000;
    const FEE_AMOUNT_FOR_CREATE_POOL: u64 = 1 * 1_000_000_000; // 100 SUI
    #[test_only]
    const PREVENT_SELF_MATCHING_DEFAULT: u8 = 0;

    // <<<<<<<<<<<<<<<<<<<<<<<< Constants <<<<<<<<<<<<<<<<<<<<<<<<

    // <<<<<<<<<<<<<<<<<<<<<<<< Events <<<<<<<<<<<<<<<<<<<<<<<<

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
        lot_size: u64, // lot_size in this context is the minimum trade size.
    }

    /// Emitted when a maker order is injected into the order book.
    public struct OrderPlaced<phantom BaseAsset, phantom QuoteAsset> has copy, store, drop {
        /// object ID of the pool the order was placed on
        pool_id: ID,
        /// ID of the order within the pool
        order_id: u64,
        /// ID of the order defined by client
        client_order_id: u64,
        is_bid: bool,
        /// owner ID of the `AccountCap` that placed the order
        owner: address,
        original_quantity: u64,
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
        /// ID of the order defined by client
        client_order_id: u64,
        is_bid: bool,
        /// owner ID of the `AccountCap` that canceled the order
        owner: address,
        original_quantity: u64,
        base_asset_quantity_canceled: u64,
        price: u64
    }

    /// A struct to make all orders canceled a more effifient struct
    public struct AllOrdersCanceledComponent<phantom BaseAsset, phantom QuoteAsset> has copy, store, drop {
        /// ID of the order within the pool
        order_id: u64,
        /// ID of the order defined by client
        client_order_id: u64,
        is_bid: bool,
        /// owner ID of the `AccountCap` that canceled the order
        owner: address,
        original_quantity: u64,
        base_asset_quantity_canceled: u64,
        price: u64
    }

    /// Emitted when batch of orders are canceled.
    public struct AllOrdersCanceled<phantom BaseAsset, phantom QuoteAsset> has copy, store, drop {
        /// object ID of the pool the order was placed on
        pool_id: ID,
        orders_canceled: vector<AllOrdersCanceledComponent<BaseAsset, QuoteAsset>>,
    }

    /// Emitted only when a maker order is filled.
    public struct OrderFilled<phantom BaseAsset, phantom QuoteAsset> has copy, store, drop {
        /// object ID of the pool the order was placed on
        pool_id: ID,
        /// ID of the order within the pool
        order_id: u64,
        /// ID of the order defined by taker client
        taker_client_order_id: u64,
        /// ID of the order defined by maker client
        maker_client_order_id: u64,
        is_bid: bool,
        /// owner ID of the `AccountCap` that filled the order
        taker_address: address,
        /// owner ID of the `AccountCap` that placed the order
        maker_address: address,
        original_quantity: u64,
        base_asset_quantity_filled: u64,
        base_asset_quantity_remaining: u64,
        price: u64,
        taker_commission: u64,
        maker_rebates: u64
    }

    /// Emitted when user deposit asset to custodian
    public struct DepositAsset<phantom Asset> has copy, store, drop {
        /// object id of the pool that asset deposit to
        pool_id: ID,
        /// quantity of the asset deposited
        quantity: u64,
        /// owner address of the `AccountCap` that deposit the asset
        owner: address
    }

    /// Emitted when user withdraw asset from custodian
    public struct WithdrawAsset<phantom Asset> has copy, store, drop {
        /// object id of the pool that asset withdraw from
        pool_id: ID,
        /// quantity of the asset user withdrew
        quantity: u64,
        /// owner ID of the `AccountCap` that withdrew the asset
        owner: address
    }

    /// Returned as metadata only when a maker order is filled from place order functions.
    public struct MatchedOrderMetadata<phantom BaseAsset, phantom QuoteAsset> has copy, store, drop {
        /// object ID of the pool the order was placed on
        pool_id: ID,
        /// ID of the order within the pool
        order_id: u64,
        /// Direction of order.
        is_bid: bool,
        /// owner ID of the `AccountCap` that filled the order
        taker_address: address,
        /// owner ID of the `AccountCap` that placed the order
        maker_address: address,
        /// qty of base asset filled.
        base_asset_quantity_filled: u64,
        /// price at which basset asset filled.
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
        // The highest bit of the order id is used to denote the order type, 0 for bid, 1 for ask.
        order_id: u64,
        client_order_id: u64,
        // Only used for limit orders.
        price: u64,
        // quantity when the order first placed in
        original_quantity: u64,
        // quantity of the order currently held
        quantity: u64,
        is_bid: bool,
        /// Order can only be canceled by the `AccountCap` with this owner ID
        owner: address,
        // Expiration timestamp in ms.
        expire_timestamp: u64,
        // reserved field for prevent self_matching
        self_matching_prevention: u8
    }

    public struct TickLevel has store {
        price: u64,
        // The key is order's order_id.
        open_orders: LinkedTable<u64, Order>,
    }

    public struct Pool<phantom BaseAsset, phantom QuoteAsset> has key, store {
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
        // Map from AccountCap owner ID -> (map from order id -> order price)
        usr_open_orders: Table<address, LinkedTable<u64, u64>>,
        // taker_fee_rate should be strictly greater than maker_rebate_rate.
        // The difference between taker_fee_rate and maker_rabate_rate goes to the protocol.
        // 10^9 scaling
        taker_fee_rate: u64,
        // 10^9 scaling
        maker_rebate_rate: u64,
        tick_size: u64,
        lot_size: u64, // lot_size in this context is the minimum trade size.
        // other pool info
        base_custodian: Custodian<BaseAsset>,
        quote_custodian: Custodian<QuoteAsset>,
        // Stores the fee paid to create this pool. These funds are not accessible.
        creation_fee: Balance<SUI>,
        // Deprecated.
        base_asset_trading_fees: Balance<BaseAsset>,
        // Stores the trading fees paid in `QuoteAsset`. These funds are not accessible in the V1 of the Pools, but V2 Pools are accessible.
        quote_asset_trading_fees: Balance<QuoteAsset>,
    }

    /// Capability granting permission to access an entry in `Pool.quote_asset_trading_fees`.
    /// The pool objects created for older pools do not have a PoolOwnerCap because they were created
    /// prior to the addition of this feature. Here is a list of 11 pools on mainnet that
    /// do not have this capability:
    /// 0x31d1790e617eef7f516555124155b28d663e5c600317c769a75ee6336a54c07f
    /// 0x6e417ee1c12ad5f2600a66bc80c7bd52ff3cb7c072d508700d17cf1325324527
    /// 0x17625f1a241d34d2da0dc113086f67a2b832e3e8cd8006887c195cd24d3598a3
    /// 0x276ff4d99ecb3175091ba4baffa9b07590f84e2344e3f16e95d30d2c1678b84c
    /// 0xd1f0a9baacc1864ab19534e2d4c5d6c14f2e071a1f075e8e7f9d51f2c17dc238
    /// 0x4405b50d791fd3346754e8171aaab6bc2ed26c2c46efdd033c14b30ae507ac33
    /// 0xf0f663cf87f1eb124da2fc9be813e0ce262146f3df60bc2052d738eb41a25899
    /// 0xd9e45ab5440d61cc52e3b2bd915cdd643146f7593d587c715bc7bfa48311d826
    /// 0x5deafda22b6b86127ea4299503362638bea0ca33bb212ea3a67b029356b8b955
    /// 0x7f526b1263c4b91b43c9e646419b5696f424de28dda3c1e6658cc0a54558baa7
    /// 0x18d871e3c3da99046dfc0d3de612c5d88859bc03b8f0568bd127d0e70dbc58be
    public struct PoolOwnerCap has key, store {
        id: UID,
        /// The owner of this AccountCap. Note: this is
        /// derived from an object ID, not a user address
        owner: address
    }

    /// Accessor functions
    public fun usr_open_orders_exist<BaseAsset, QuoteAsset>(
        pool: &Pool<BaseAsset, QuoteAsset>,
        owner: address
    ): bool {
        table::contains(&pool.usr_open_orders, owner)
    }

    public fun usr_open_orders_for_address<BaseAsset, QuoteAsset>(
        pool: &Pool<BaseAsset, QuoteAsset>,
        owner: address
    ): &LinkedTable<u64, u64> {
        table::borrow(&pool.usr_open_orders, owner)
    }

    public fun usr_open_orders<BaseAsset, QuoteAsset>(
        pool: &Pool<BaseAsset, QuoteAsset>,
    ): &Table<address, LinkedTable<u64, u64>> {
        &pool.usr_open_orders
    }

    /// Function to withdraw fees created from a pool
    public fun withdraw_fees<BaseAsset, QuoteAsset>(
        pool_owner_cap: &PoolOwnerCap,
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        ctx: &mut TxContext,
    ): Coin<QuoteAsset> {
        assert!(pool_owner_cap.owner == object::uid_to_address(&pool.id), EIncorrectPoolOwner);
        let quantity = quote_asset_trading_fees_value(pool);
        let to_withdraw = balance::split(&mut pool.quote_asset_trading_fees, quantity);
        coin::from_balance(to_withdraw, ctx)
    }

    /// Destroy the given `pool_owner_cap` object
    public fun delete_pool_owner_cap(pool_owner_cap: PoolOwnerCap) {
        let PoolOwnerCap { id, owner: _ } = pool_owner_cap;
        object::delete(id)
    }

    fun destroy_empty_level(level: TickLevel) {
        let TickLevel {
            price: _,
            open_orders: orders,
        } = level;

        linked_table::destroy_empty(orders);
    }

    public fun create_account(ctx: &mut TxContext): AccountCap {
        mint_account_cap(ctx)
    }

    #[allow(lint(self_transfer, share_owned))]
    fun create_pool_<BaseAsset, QuoteAsset>(
        taker_fee_rate: u64,
        maker_rebate_rate: u64,
        tick_size: u64,
        min_size: u64,
        creation_fee: Balance<SUI>,
        ctx: &mut TxContext,
    ) {
        let (pool, pool_owner_cap) = create_pool_with_return_<BaseAsset, QuoteAsset>(
            taker_fee_rate,
            maker_rebate_rate,
            tick_size,
            min_size,
            creation_fee,
            ctx
        );

        transfer::public_transfer(pool_owner_cap, tx_context::sender(ctx));
        transfer::share_object(pool);
    }

    public fun create_pool<BaseAsset, QuoteAsset>(
        tick_size: u64,
        min_size: u64,
        creation_fee: Coin<SUI>,
        ctx: &mut TxContext,
    ) {
        create_customized_pool<BaseAsset, QuoteAsset>(
            tick_size,
            min_size,
            REFERENCE_TAKER_FEE_RATE,
            REFERENCE_MAKER_REBATE_RATE,
            creation_fee,
            ctx,
        );
    }

    /// Function for creating pool with customized taker fee rate and maker rebate rate.
    /// The taker_fee_rate should be greater than or equal to the maker_rebate_rate, and both should have a scaling of 10^9.
    /// Taker_fee_rate of 0.25% should be 2_500_000 for example
    public fun create_customized_pool<BaseAsset, QuoteAsset>(
        tick_size: u64,
        min_size: u64,
        taker_fee_rate: u64,
        maker_rebate_rate: u64,
        creation_fee: Coin<SUI>,
        ctx: &mut TxContext,
    ) {
        create_pool_<BaseAsset, QuoteAsset>(
            taker_fee_rate,
            maker_rebate_rate,
            tick_size,
            min_size,
            coin::into_balance(creation_fee),
            ctx
        )
    }

    /// Helper function that all the create pools now call to create pools.
    fun create_pool_with_return_<BaseAsset, QuoteAsset>(
        taker_fee_rate: u64,
        maker_rebate_rate: u64,
        tick_size: u64,
        min_size: u64,
        creation_fee: Balance<SUI>,
        ctx: &mut TxContext,
    ): (Pool<BaseAsset, QuoteAsset>, PoolOwnerCap) {
        assert!(balance::value(&creation_fee) == FEE_AMOUNT_FOR_CREATE_POOL, EInvalidFee);

        let base_type_name = type_name::get<BaseAsset>();
        let quote_type_name = type_name::get<QuoteAsset>();

        assert!(clob_math::unsafe_mul(min_size, tick_size) > 0, EInvalidTickSizeMinSize);
        assert!(base_type_name != quote_type_name, EInvalidPair);
        assert!(taker_fee_rate >= maker_rebate_rate, EInvalidFeeRateRebateRate);

        let pool_uid = object::new(ctx);
        let pool_id = *object::uid_as_inner(&pool_uid);

        // Creates the capability to mark a pool owner.
        let id = object::new(ctx);
        let owner = object::uid_to_address(&pool_uid);
        let pool_owner_cap = PoolOwnerCap { id, owner };

        event::emit(PoolCreated {
            pool_id,
            base_asset: base_type_name,
            quote_asset: quote_type_name,
            taker_fee_rate,
            maker_rebate_rate,
            tick_size,
            lot_size: min_size,
        });
        (Pool<BaseAsset, QuoteAsset> {
            id: pool_uid,
            bids: critbit::new(ctx),
            asks: critbit::new(ctx),
            next_bid_order_id: MIN_BID_ORDER_ID,
            next_ask_order_id: MIN_ASK_ORDER_ID,
            usr_open_orders: table::new(ctx),
            taker_fee_rate,
            maker_rebate_rate,
            tick_size,
            lot_size: min_size,
            base_custodian: custodian::new<BaseAsset>(ctx),
            quote_custodian: custodian::new<QuoteAsset>(ctx),
            creation_fee,
            base_asset_trading_fees: balance::zero(),
            quote_asset_trading_fees: balance::zero(),
        }, pool_owner_cap)
    }

    /// Function for creating an external pool. This API can be used to wrap deepbook pools into other objects.
    public fun create_pool_with_return<BaseAsset, QuoteAsset>(
        tick_size: u64,
        min_size: u64,
        creation_fee: Coin<SUI>,
        ctx: &mut TxContext,
    ): Pool<BaseAsset, QuoteAsset> {
        create_customized_pool_with_return<BaseAsset, QuoteAsset>(
            tick_size,
            min_size,
            REFERENCE_TAKER_FEE_RATE,
            REFERENCE_MAKER_REBATE_RATE,
            creation_fee,
            ctx,
        )
    }

    #[allow(lint(self_transfer))]
    /// Function for creating pool with customized taker fee rate and maker rebate rate.
    /// The taker_fee_rate should be greater than or equal to the maker_rebate_rate, and both should have a scaling of 10^9.
    /// Taker_fee_rate of 0.25% should be 2_500_000 for example
    public fun create_customized_pool_with_return<BaseAsset, QuoteAsset>(
        tick_size: u64,
        min_size: u64,
        taker_fee_rate: u64,
        maker_rebate_rate: u64,
        creation_fee: Coin<SUI>,
        ctx: &mut TxContext,
    ) : Pool<BaseAsset, QuoteAsset> {
        let (pool, pool_owner_cap) = create_pool_with_return_<BaseAsset, QuoteAsset>(
            taker_fee_rate,
            maker_rebate_rate,
            tick_size,
            min_size,
            coin::into_balance(creation_fee),
            ctx
        );
        transfer::public_transfer(pool_owner_cap, tx_context::sender(ctx));
        pool
    }

    /// A V2 function for creating customized pools for better PTB friendliness/compostability.
    /// If a user wants to create a pool and then destroy/lock the pool_owner_cap one can do
    /// so with this function.
    public fun create_customized_pool_v2<BaseAsset, QuoteAsset>(
        tick_size: u64,
        min_size: u64,
        taker_fee_rate: u64,
        maker_rebate_rate: u64,
        creation_fee: Coin<SUI>,
        ctx: &mut TxContext,
    ) : (Pool<BaseAsset, QuoteAsset>, PoolOwnerCap) {
        create_pool_with_return_<BaseAsset, QuoteAsset>(
            taker_fee_rate,
            maker_rebate_rate,
            tick_size,
            min_size,
            coin::into_balance(creation_fee),
            ctx
        )
    }

    public fun deposit_base<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        coin: Coin<BaseAsset>,
        account_cap: &AccountCap
    ) {
        let quantity = coin::value(&coin);
        assert!(quantity != 0, EInsufficientBaseCoin);
        custodian::increase_user_available_balance(
            &mut pool.base_custodian,
            account_owner(account_cap),
            coin::into_balance(coin)
        );
        event::emit(DepositAsset<BaseAsset>{
            pool_id: *object::uid_as_inner(&pool.id),
            quantity,
            owner: account_owner(account_cap)
        })
    }

    public fun deposit_quote<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        coin: Coin<QuoteAsset>,
        account_cap: &AccountCap
    ) {
        let quantity = coin::value(&coin);
        assert!(quantity != 0, EInsufficientQuoteCoin);
        custodian::increase_user_available_balance(
            &mut pool.quote_custodian,
            account_owner(account_cap),
            coin::into_balance(coin)
        );
        event::emit(DepositAsset<QuoteAsset>{
            pool_id: *object::uid_as_inner(&pool.id),
            quantity,
            owner: account_owner(account_cap)
        })
    }

    public fun withdraw_base<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        quantity: u64,
        account_cap: &AccountCap,
        ctx: &mut TxContext
    ): Coin<BaseAsset> {
        assert!(quantity > 0, EInvalidQuantity);
        event::emit(WithdrawAsset<BaseAsset>{
            pool_id: *object::uid_as_inner(&pool.id),
            quantity,
            owner: account_owner(account_cap)
        });
        custodian::withdraw_asset(&mut pool.base_custodian, quantity, account_cap, ctx)
    }

    public fun withdraw_quote<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        quantity: u64,
        account_cap: &AccountCap,
        ctx: &mut TxContext
    ): Coin<QuoteAsset> {
        assert!(quantity > 0, EInvalidQuantity);
        event::emit(WithdrawAsset<QuoteAsset>{
            pool_id: *object::uid_as_inner(&pool.id),
            quantity,
            owner: account_owner(account_cap)
        });
        custodian::withdraw_asset(&mut pool.quote_custodian, quantity, account_cap, ctx)
    }

    // for smart routing
    public fun swap_exact_base_for_quote<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        client_order_id: u64,
        account_cap: &AccountCap,
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
            account_cap,
            client_order_id,
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
    public fun swap_exact_base_for_quote_with_metadata<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        client_order_id: u64,
        account_cap: &AccountCap,
        quantity: u64,
        base_coin: Coin<BaseAsset>,
        quote_coin: Coin<QuoteAsset>,
        clock: &Clock,
        ctx: &mut TxContext,
    ): (Coin<BaseAsset>, Coin<QuoteAsset>, u64, vector<MatchedOrderMetadata<BaseAsset, QuoteAsset>>) {
        let original_val = coin::value(&quote_coin);
        let (ret_base_coin, ret_quote_coin, mut matched_order_metadata) = place_market_order_int(
            pool,
            account_cap,
            client_order_id,
            quantity,
            false,
            base_coin,
            quote_coin,
            clock,
            true, // return metadata
            ctx
        );
        let ret_val = coin::value(&ret_quote_coin);
        (ret_base_coin, ret_quote_coin, ret_val - original_val, option::extract(&mut matched_order_metadata))
    }

    // for smart routing
    public fun swap_exact_quote_for_base<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        client_order_id: u64,
        account_cap: &AccountCap,
        quantity: u64,
        clock: &Clock,
        quote_coin: Coin<QuoteAsset>,
        ctx: &mut TxContext,
    ): (Coin<BaseAsset>, Coin<QuoteAsset>, u64) {
        assert!(quantity > 0, EInvalidQuantity);
        assert!(coin::value(&quote_coin) >= quantity, EInsufficientQuoteCoin);
        let (base_asset_balance, quote_asset_balance, _matched_order_metadata) = match_bid_with_quote_quantity(
            pool,
            account_cap,
            client_order_id,
            quantity,
            MAX_PRICE,
            clock::timestamp_ms(clock),
            coin::into_balance(quote_coin),
            false // don't return metadata
        );
        let val = balance::value(&base_asset_balance);
        (coin::from_balance(base_asset_balance, ctx), coin::from_balance(quote_asset_balance, ctx), val)
    }

    public fun swap_exact_quote_for_base_with_metadata<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        client_order_id: u64,
        account_cap: &AccountCap,
        quantity: u64,
        clock: &Clock,
        quote_coin: Coin<QuoteAsset>,
        ctx: &mut TxContext,
    ): (Coin<BaseAsset>, Coin<QuoteAsset>, u64, vector<MatchedOrderMetadata<BaseAsset, QuoteAsset>>) {
        assert!(quantity > 0, EInvalidQuantity);
        assert!(coin::value(&quote_coin) >= quantity, EInsufficientQuoteCoin);
        let (base_asset_balance, quote_asset_balance, mut matched_order_metadata) = match_bid_with_quote_quantity(
            pool,
            account_cap,
            client_order_id,
            quantity,
            MAX_PRICE,
            clock::timestamp_ms(clock),
            coin::into_balance(quote_coin),
            true // return metadata
        );
        let val = balance::value(&base_asset_balance);
        (coin::from_balance(base_asset_balance, ctx), coin::from_balance(quote_asset_balance, ctx), val, option::extract(&mut matched_order_metadata))
    }

    fun match_bid_with_quote_quantity<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        account_cap: &AccountCap,
        client_order_id: u64,
        quantity: u64,
        price_limit: u64,
        current_timestamp: u64,
        quote_balance: Balance<QuoteAsset>,
        compute_metadata: bool,
    ): (Balance<BaseAsset>, Balance<QuoteAsset>, Option<vector<MatchedOrderMetadata<BaseAsset, QuoteAsset>>>) {
        // Base balance received by taker, taking into account of taker commission.
        // Need to individually keep track of the remaining base quantity to be filled to avoid infinite loop.
        let pool_id = *object::uid_as_inner(&pool.id);
        let mut taker_quote_quantity_remaining = quantity;
        let mut base_balance_filled = balance::zero<BaseAsset>();
        let mut quote_balance_left = quote_balance;
        let all_open_orders = &mut pool.asks;
        let mut matched_order_metadata = vector::empty<MatchedOrderMetadata<BaseAsset, QuoteAsset>>();
        if (critbit::is_empty(all_open_orders)) {
            return (base_balance_filled, quote_balance_left, option::none())
        };
        let (mut tick_price, mut tick_index) = min_leaf(all_open_orders);
        let mut terminate_loop = false;
        let mut canceled_order_events = vector[];

        while (!is_empty<TickLevel>(all_open_orders) && tick_price <= price_limit) {
            let tick_level = borrow_mut_leaf_by_index(all_open_orders, tick_index);
            let mut order_id = *option::borrow(linked_table::front(&tick_level.open_orders));

            while (!linked_table::is_empty(&tick_level.open_orders)) {
                let maker_order = linked_table::borrow(&tick_level.open_orders, order_id);
                let mut maker_base_quantity = maker_order.quantity;
                let mut skip_order = false;

                if (maker_order.expire_timestamp <= current_timestamp || account_owner(account_cap) == maker_order.owner) {
                    skip_order = true;
                    custodian::unlock_balance(&mut pool.base_custodian, maker_order.owner, maker_order.quantity);
                    let canceled_order_event = AllOrdersCanceledComponent<BaseAsset, QuoteAsset> {
                        client_order_id: maker_order.client_order_id,
                        order_id: maker_order.order_id,
                        is_bid: maker_order.is_bid,
                        owner: maker_order.owner,
                        original_quantity: maker_order.original_quantity,
                        base_asset_quantity_canceled: maker_order.quantity,
                        price: maker_order.price
                    };

                    vector::push_back(&mut canceled_order_events, canceled_order_event);

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
                        let filled_base_lot = filled_base_quantity / LOT_SIZE;
                        filled_base_quantity = filled_base_lot * LOT_SIZE;
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
                        client_order_id,
                        account_owner(account_cap),
                        maker_order,
                        filled_base_quantity,
                        // taker_commission = filled_quote_quantity - filled_quote_quantity_without_commission
                        // This guarantees that the subtraction will not underflow
                        filled_quote_quantity - filled_quote_quantity_without_commission,
                        maker_rebate
                    );
                    if(compute_metadata) {
                        vector::push_back(
                            &mut matched_order_metadata,
                            matched_order_metadata(
                                *object::uid_as_inner(&pool.id),
                                account_owner(account_cap),
                                maker_order,
                                filled_base_quantity,
                                // taker_commission = filled_quote_quantity - filled_quote_quantity_without_commission
                                // This guarantees that the subtraction will not underflow
                                filled_quote_quantity - filled_quote_quantity_without_commission,
                                maker_rebate
                            )
                        );
                    };
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

        if (!vector::is_empty(&canceled_order_events)) {
            event::emit(AllOrdersCanceled<BaseAsset, QuoteAsset> {
                pool_id,
                orders_canceled: canceled_order_events,
            });
        };

        return (base_balance_filled, quote_balance_left, if(compute_metadata) option::some(matched_order_metadata) else option::none())
    }

    fun match_bid<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        account_cap: &AccountCap,
        client_order_id: u64,
        quantity: u64,
        price_limit: u64,
        current_timestamp: u64,
        quote_balance: Balance<QuoteAsset>,
        compute_metadata: bool,
    ): (Balance<BaseAsset>, Balance<QuoteAsset>, Option<vector<MatchedOrderMetadata<BaseAsset, QuoteAsset>>>) {
        let pool_id = *object::uid_as_inner(&pool.id);
        // Base balance received by taker.
        // Need to individually keep track of the remaining base quantity to be filled to avoid infinite loop.
        let mut taker_base_quantity_remaining = quantity;
        let mut base_balance_filled = balance::zero<BaseAsset>();
        let mut quote_balance_left = quote_balance;
        let all_open_orders = &mut pool.asks;
        let mut matched_order_metadata = vector::empty<MatchedOrderMetadata<BaseAsset, QuoteAsset>>();
        if (critbit::is_empty(all_open_orders)) {
            return (base_balance_filled, quote_balance_left, option::none())
        };
        let (mut tick_price, mut tick_index) = min_leaf(all_open_orders);
        let mut canceled_order_events = vector[];

        while (!is_empty<TickLevel>(all_open_orders) && tick_price <= price_limit) {
            let tick_level = borrow_mut_leaf_by_index(all_open_orders, tick_index);
            let mut order_id = *option::borrow(linked_table::front(&tick_level.open_orders));

            while (!linked_table::is_empty(&tick_level.open_orders)) {
                let maker_order = linked_table::borrow(&tick_level.open_orders, order_id);
                let mut maker_base_quantity = maker_order.quantity;
                let mut skip_order = false;

                if (maker_order.expire_timestamp <= current_timestamp || account_owner(account_cap) == maker_order.owner) {
                    skip_order = true;
                    custodian::unlock_balance(&mut pool.base_custodian, maker_order.owner, maker_order.quantity);
                    let canceled_order_event = AllOrdersCanceledComponent<BaseAsset, QuoteAsset> {
                        client_order_id: maker_order.client_order_id,
                        order_id: maker_order.order_id,
                        is_bid: maker_order.is_bid,
                        owner: maker_order.owner,
                        original_quantity: maker_order.original_quantity,
                        base_asset_quantity_canceled: maker_order.quantity,
                        price: maker_order.price
                    };
                    vector::push_back(&mut canceled_order_events, canceled_order_event);

                } else {
                    let filled_base_quantity =
                        if (taker_base_quantity_remaining > maker_base_quantity) { maker_base_quantity }
                        else { taker_base_quantity_remaining };
                    // Note that if a user creates a pool that allows orders that are too small, this will fail since we cannot have a filled
                    // quote quantity of 0.
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
                        client_order_id,
                        account_owner(account_cap),
                        maker_order,
                        filled_base_quantity,
                        taker_commission,
                        maker_rebate
                    );
                    if(compute_metadata){
                        vector::push_back(
                            &mut matched_order_metadata,
                            matched_order_metadata(
                                *object::uid_as_inner(&pool.id),
                                account_owner(account_cap),
                                maker_order,
                                filled_base_quantity,
                                taker_commission,
                                maker_rebate
                            )
                        );
                    };
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

        if (!vector::is_empty(&canceled_order_events)) {
            event::emit(AllOrdersCanceled<BaseAsset, QuoteAsset> {
                pool_id,
                orders_canceled: canceled_order_events,
            });
        };
        return (base_balance_filled, quote_balance_left, if(compute_metadata) option::some(matched_order_metadata) else option::none())
    }

    fun match_ask<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        account_cap: &AccountCap,
        client_order_id: u64,
        price_limit: u64,
        current_timestamp: u64,
        base_balance: Balance<BaseAsset>,
        compute_metadata: bool,
    ): (Balance<BaseAsset>, Balance<QuoteAsset>, Option<vector<MatchedOrderMetadata<BaseAsset, QuoteAsset>>>) {
        let pool_id = *object::uid_as_inner(&pool.id);
        let mut base_balance_left = base_balance;
        // Base balance received by taker, taking into account of taker commission.
        let mut quote_balance_filled = balance::zero<QuoteAsset>();
        let all_open_orders = &mut pool.bids;
        let mut matched_order_metadata = vector::empty<MatchedOrderMetadata<BaseAsset, QuoteAsset>>();
        if (critbit::is_empty(all_open_orders)) {
            return (base_balance_left, quote_balance_filled, option::none())
        };
        let (mut tick_price, mut tick_index) = max_leaf(all_open_orders);
        let mut canceled_order_events = vector[];
        while (!is_empty<TickLevel>(all_open_orders) && tick_price >= price_limit) {
            let tick_level = borrow_mut_leaf_by_index(all_open_orders, tick_index);
            let mut order_id = *option::borrow(linked_table::front(&tick_level.open_orders));
            while (!linked_table::is_empty(&tick_level.open_orders)) {
                let maker_order = linked_table::borrow(&tick_level.open_orders, order_id);
                let mut maker_base_quantity = maker_order.quantity;
                let mut skip_order = false;

                if (maker_order.expire_timestamp <= current_timestamp || account_owner(account_cap) == maker_order.owner) {
                    skip_order = true;
                    let maker_quote_quantity = clob_math::mul(maker_order.quantity, maker_order.price);
                    custodian::unlock_balance(&mut pool.quote_custodian, maker_order.owner, maker_quote_quantity);
                    let canceled_order_event = AllOrdersCanceledComponent<BaseAsset, QuoteAsset> {
                        client_order_id: maker_order.client_order_id,
                        order_id: maker_order.order_id,
                        is_bid: maker_order.is_bid,
                        owner: maker_order.owner,
                        original_quantity: maker_order.original_quantity,
                        base_asset_quantity_canceled: maker_order.quantity,
                        price: maker_order.price
                    };
                    vector::push_back(&mut canceled_order_events, canceled_order_event);
                } else {
                    let taker_base_quantity_remaining = balance::value(&base_balance_left);
                    let filled_base_quantity =
                        if (taker_base_quantity_remaining >= maker_base_quantity) { maker_base_quantity }
                        else { taker_base_quantity_remaining };
                    // If a bit is rounded down, the pool will take this as a fee.
                    let (is_round_down, filled_quote_quantity) = clob_math::unsafe_mul_round(filled_base_quantity, maker_order.price);
                    if (is_round_down) {
                        let rounded_down_quantity = custodian::decrease_user_locked_balance<QuoteAsset>(
                            &mut pool.quote_custodian,
                            maker_order.owner,
                            1
                        );
                        balance::join(&mut pool.quote_asset_trading_fees, rounded_down_quantity);
                    };

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
                        client_order_id,
                        account_owner(account_cap),
                        maker_order,
                        filled_base_quantity,
                        taker_commission,
                        maker_rebate
                    );
                    if(compute_metadata) {
                        vector::push_back(
                            &mut matched_order_metadata,
                            matched_order_metadata(
                                *object::uid_as_inner(&pool.id),
                                account_owner(account_cap),
                                maker_order,
                                filled_base_quantity,
                                taker_commission,
                                maker_rebate
                            )
                        );
                    }
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

        if (!vector::is_empty(&canceled_order_events)) {
            event::emit(AllOrdersCanceled<BaseAsset, QuoteAsset> {
                pool_id,
                orders_canceled: canceled_order_events,
            });
        };

        return (base_balance_left, quote_balance_filled, if(compute_metadata) option::some(matched_order_metadata) else option::none())
    }

    /// Place a market order to the order book.
    public fun place_market_order<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        account_cap: &AccountCap,
        client_order_id: u64,
        quantity: u64,
        is_bid: bool,
        base_coin: Coin<BaseAsset>,
        quote_coin: Coin<QuoteAsset>,
        clock: &Clock,
        ctx: &mut TxContext,
    ): (Coin<BaseAsset>, Coin<QuoteAsset>) {
        let (base_coin, quote_coin, _metadata) = place_market_order_int(
            pool,
            account_cap,
            client_order_id,
            quantity,
            is_bid,
            base_coin,
            quote_coin,
            clock,
            false, // don't return metadata
            ctx
        );
        (base_coin, quote_coin)
    }

    public fun place_market_order_with_metadata<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        account_cap: &AccountCap,
        client_order_id: u64,
        quantity: u64,
        is_bid: bool,
        base_coin: Coin<BaseAsset>,
        quote_coin: Coin<QuoteAsset>,
        clock: &Clock,
        ctx: &mut TxContext,
    ): (Coin<BaseAsset>, Coin<QuoteAsset>, vector<MatchedOrderMetadata<BaseAsset, QuoteAsset>>) {
        let (base_coin, quote_coin, mut metadata) = place_market_order_int(
            pool,
            account_cap,
            client_order_id,
            quantity,
            is_bid,
            base_coin,
            quote_coin,
            clock,
            true, // return metadata
            ctx
        );
        (base_coin, quote_coin, option::extract(&mut metadata))
    }

    /// Place a market order to the order book.
    fun place_market_order_int<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        account_cap: &AccountCap,
        client_order_id: u64,
        quantity: u64,
        is_bid: bool,
        mut base_coin: Coin<BaseAsset>,
        mut quote_coin: Coin<QuoteAsset>,
        clock: &Clock,
        compute_metadata: bool,
        ctx: &mut TxContext,
    ): (Coin<BaseAsset>, Coin<QuoteAsset>, Option<vector<MatchedOrderMetadata<BaseAsset, QuoteAsset>>>) {
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
        // We start with the bid PriceLevel with the highest price by calling max_leaf on the bids Critbit Tree.
        // The inner loop for iterating over the open orders in ascending orders of order id is the same as above.
        // Then iterate over the price levels in descending order until the market order is completely filled.
        let min_size = pool.lot_size;
        assert!(quantity >= min_size && quantity % LOT_SIZE == 0, EInvalidQuantity);
        assert!(quantity != 0, EInvalidQuantity);
        let metadata;
        if (is_bid) {
            let (base_balance_filled, quote_balance_left, matched_order_metadata) = match_bid(
                pool,
                account_cap,
                client_order_id,
                quantity,
                MAX_PRICE,
                clock::timestamp_ms(clock),
                coin::into_balance(quote_coin),
                compute_metadata
            );
            join(
                &mut base_coin,
                coin::from_balance(base_balance_filled, ctx),
            );
            quote_coin = coin::from_balance(quote_balance_left, ctx);
            metadata = matched_order_metadata;
        } else {
            assert!(quantity <= coin::value(&base_coin), EInsufficientBaseCoin);
            let base_coin_to_sell = coin::split(&mut base_coin, quantity, ctx);
            let (base_balance_left, quote_balance_filled, matched_order_metadata) = match_ask(
                pool,
                account_cap,
                client_order_id,
                MIN_PRICE,
                clock::timestamp_ms(clock),
                coin::into_balance(base_coin_to_sell),
                compute_metadata
            );
            join(
                &mut base_coin,
                coin::from_balance(base_balance_left, ctx));
            join(
                &mut quote_coin,
                coin::from_balance(quote_balance_filled, ctx),
            );
            metadata = matched_order_metadata;
        };
        (base_coin, quote_coin, metadata)
    }

    /// Injects a maker order to the order book.
    /// Returns the order id.
    fun inject_limit_order<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        client_order_id: u64,
        price: u64,
        original_quantity: u64,
        quantity: u64,
        is_bid: bool,
        self_matching_prevention: u8,
        expire_timestamp: u64,
        account_cap: &AccountCap,
        ctx: &mut TxContext
    ): u64 {
        let owner = account_owner(account_cap);
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
            client_order_id,
            price,
            original_quantity,
            quantity,
            is_bid,
            owner,
            expire_timestamp,
            self_matching_prevention
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
        event::emit(OrderPlaced<BaseAsset, QuoteAsset> {
            pool_id: *object::uid_as_inner(&pool.id),
            order_id,
            client_order_id,
            is_bid,
            owner,
            original_quantity,
            base_asset_quantity_placed: quantity,
            price,
            expire_timestamp
        });
        if (!contains(&pool.usr_open_orders, owner)) {
            add(&mut pool.usr_open_orders, owner, linked_table::new(ctx));
        };
        linked_table::push_back(borrow_mut(&mut pool.usr_open_orders, owner), order_id, price);

        return order_id
    }

    /// Place a limit order to the order book.
    /// Returns (base quantity filled, quote quantity filled, whether a maker order is being placed, order id of the maker order).
    /// When the limit order is not successfully placed, we return false to indicate that and also returns a meaningless order_id 0.
    /// When the limit order is successfully placed, we return true to indicate that and also the corresponding order_id.
    /// So please check that boolean value first before using the order id.
    public fun place_limit_order<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        client_order_id: u64,
        price: u64,
        quantity: u64,
        self_matching_prevention: u8,
        is_bid: bool,
        expire_timestamp: u64, // Expiration timestamp in ms in absolute value inclusive.
        restriction: u8,
        clock: &Clock,
        account_cap: &AccountCap,
        ctx: &mut TxContext
    ): (u64, u64, bool, u64) {
        let (base_quantity_filled, quote_quantity_filled, is_success, order_id, _meta_data) = place_limit_order_int(
            pool,
            client_order_id,
            price,
            quantity,
            self_matching_prevention,
            is_bid,
            expire_timestamp, // Expiration timestamp in ms in absolute value inclusive.
            restriction,
            clock,
            account_cap,
            false, // don't compute metadata
            ctx
        );
        (base_quantity_filled, quote_quantity_filled, is_success, order_id)
    }

    /// Place a limit order to the order book.
    /// Returns (base quantity filled, quote quantity filled, whether a maker order is being placed, order id of the maker order).
    /// When the limit order is not successfully placed, we return false to indicate that and also returns a meaningless order_id 0.
    /// When the limit order is successfully placed, we return true to indicate that and also the corresponding order_id.
    /// So please check that boolean value first before using the order id.
    public fun place_limit_order_with_metadata<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        client_order_id: u64,
        price: u64,
        quantity: u64,
        self_matching_prevention: u8,
        is_bid: bool,
        expire_timestamp: u64, // Expiration timestamp in ms in absolute value inclusive.
        restriction: u8,
        clock: &Clock,
        account_cap: &AccountCap,
        ctx: &mut TxContext
    ): (u64, u64, bool, u64, vector<MatchedOrderMetadata<BaseAsset, QuoteAsset>>) {
        let (base_quantity_filled, quote_quantity_filled, is_success, order_id, mut meta_data) = place_limit_order_int(
            pool,
            client_order_id,
            price,
            quantity,
            self_matching_prevention,
            is_bid,
            expire_timestamp, // Expiration timestamp in ms in absolute value inclusive.
            restriction,
            clock,
            account_cap,
            true, // return metadata
            ctx
        );
        (base_quantity_filled, quote_quantity_filled, is_success, order_id, option::extract(&mut meta_data))
    }

    fun place_limit_order_int<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        client_order_id: u64,
        price: u64,
        quantity: u64,
        self_matching_prevention: u8,
        is_bid: bool,
        expire_timestamp: u64, // Expiration timestamp in ms in absolute value inclusive.
        restriction: u8,
        clock: &Clock,
        account_cap: &AccountCap,
        compute_metadata: bool,
        ctx: &mut TxContext
    ): (u64, u64, bool, u64, Option<vector<MatchedOrderMetadata<BaseAsset, QuoteAsset>>>) {
        // If limit bid order, check whether the price is lower than the lowest ask order by checking the min_leaf of asks Critbit Tree.
        // If so, assign the sequence id of the order to be next_bid_order_id and increment next_bid_order_id by 1.
        // Inject the new order to the bids Critbit Tree according to the price and order id.
        // Otherwise, find the price level from the asks Critbit Tree that is no greater than the input price.
        // Match the bid order against the asks Critbit Tree in the same way as a market order but up until the price level found in the previous step.
        // If the bid order is not completely filled, inject the remaining quantity to the bids Critbit Tree according to the input price and order id.
        // If limit ask order, vice versa.
        assert!(self_matching_prevention == CANCEL_OLDEST, EInvalidSelfMatchingPreventionArg);
        assert!(quantity > 0, EInvalidQuantity);
        assert!(price > 0, EInvalidPrice);
        assert!(price % pool.tick_size == 0, EInvalidPrice);
        let min_size = pool.lot_size;
        assert!(quantity >= min_size && quantity % LOT_SIZE == 0, EInvalidQuantity);
        assert!(expire_timestamp > clock::timestamp_ms(clock), EInvalidExpireTimestamp);
        let owner = account_owner(account_cap);
        let original_quantity = quantity;
        let base_quantity_filled;
        let quote_quantity_filled;
        let meta_data = if (is_bid) {
            let quote_quantity_original = custodian::account_available_balance<QuoteAsset>(
                &pool.quote_custodian,
                owner
            );
            let quote_balance = custodian::decrease_user_available_balance<QuoteAsset>(
                &mut pool.quote_custodian,
                account_cap,
                quote_quantity_original,
            );
            let (base_balance_filled, quote_balance_left, matched_order_metadata) = match_bid(
                pool,
                account_cap,
                client_order_id,
                quantity,
                price,
                clock::timestamp_ms(clock),
                quote_balance,
                compute_metadata
            );
            base_quantity_filled = balance::value(&base_balance_filled);
            quote_quantity_filled = quote_quantity_original - balance::value(&quote_balance_left);

            custodian::increase_user_available_balance<BaseAsset>(
                &mut pool.base_custodian,
                owner,
                base_balance_filled,
            );
            custodian::increase_user_available_balance<QuoteAsset>(
                &mut pool.quote_custodian,
                owner,
                quote_balance_left,
            );

            matched_order_metadata
        } else {
            let base_balance = custodian::decrease_user_available_balance<BaseAsset>(
                &mut pool.base_custodian,
                account_cap,
                quantity,
            );
            let (base_balance_left, quote_balance_filled, matched_order_metadata) = match_ask(
                pool,
                account_cap,
                client_order_id,
                price,
                clock::timestamp_ms(clock),
                base_balance,
                compute_metadata
            );

            base_quantity_filled = quantity - balance::value(&base_balance_left);
            quote_quantity_filled = balance::value(&quote_balance_filled);

            custodian::increase_user_available_balance<BaseAsset>(
                &mut pool.base_custodian,
                owner,
                base_balance_left,
            );
            custodian::increase_user_available_balance<QuoteAsset>(
                &mut pool.quote_custodian,
                owner,
                quote_balance_filled,
            );
            matched_order_metadata
        };

        let order_id;
        if (restriction == IMMEDIATE_OR_CANCEL) {
            return (base_quantity_filled, quote_quantity_filled, false, 0, meta_data)
        };
        if (restriction == FILL_OR_KILL) {
            assert!(base_quantity_filled == quantity, EOrderCannotBeFullyFilled);
            return (base_quantity_filled, quote_quantity_filled, false, 0, meta_data)
        };
        if (restriction == POST_OR_ABORT) {
            assert!(base_quantity_filled == 0, EOrderCannotBeFullyPassive);
            order_id = inject_limit_order(
                pool,
                client_order_id,
                price,
                original_quantity,
                quantity,
                is_bid,
                self_matching_prevention,
                expire_timestamp,
                account_cap,
                ctx
            );
            return (base_quantity_filled, quote_quantity_filled, true, order_id, meta_data)
        } else {
            assert!(restriction == NO_RESTRICTION, EInvalidRestriction);
            if (quantity > base_quantity_filled) {
                order_id = inject_limit_order(
                    pool,
                    client_order_id,
                    price,
                    original_quantity,
                    quantity - base_quantity_filled,
                    is_bid,
                    self_matching_prevention,
                    expire_timestamp,
                    account_cap,
                    ctx
                );
                return (base_quantity_filled, quote_quantity_filled, true, order_id, meta_data)
            };
            return (base_quantity_filled, quote_quantity_filled, false, 0, meta_data)
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
            client_order_id: order.client_order_id,
            order_id: order.order_id,
            is_bid: order.is_bid,
            owner: order.owner,
            original_quantity: order.original_quantity,
            base_asset_quantity_canceled: order.quantity,
            price: order.price
        })
    }

    fun emit_order_filled<BaseAsset, QuoteAsset>(
        pool_id: ID,
        taker_client_id: u64,
        taker_address: address,
        order: &Order,
        base_asset_quantity_filled: u64,
        taker_commission: u64,
        maker_rebates: u64
    ) {
        event::emit(OrderFilled<BaseAsset, QuoteAsset> {
            pool_id,
            order_id: order.order_id,
            taker_client_order_id: taker_client_id,
            taker_address,
            maker_client_order_id: order.client_order_id,
            is_bid: order.is_bid,
            maker_address: order.owner,
            original_quantity: order.original_quantity,
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
        let owner = account_owner(account_cap);
        assert!(contains(&pool.usr_open_orders, owner), EInvalidUser);
        let usr_open_orders = borrow_mut(&mut pool.usr_open_orders, owner);
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
            owner
        );
        if (is_bid) {
            let (_, balance_locked) = clob_math::unsafe_mul_round(order.quantity, order.price);
            custodian::unlock_balance(&mut pool.quote_custodian, owner, balance_locked);
        } else {
            custodian::unlock_balance(&mut pool.base_custodian, owner, order.quantity);
        };
        emit_order_canceled<BaseAsset, QuoteAsset>(*object::uid_as_inner(&pool.id), &order);
    }

    fun remove_order(
        open_orders: &mut CritbitTree<TickLevel>,
        usr_open_orders: &mut LinkedTable<u64, u64>,
        tick_index: u64,
        order_id: u64,
        owner: address,
    ): Order {
        linked_table::remove(usr_open_orders, order_id);
        let tick_level = borrow_leaf_by_index(open_orders, tick_index);
        assert!(linked_table::contains(&tick_level.open_orders, order_id), EInvalidOrderId);
        let mut_tick_level = borrow_mut_leaf_by_index(open_orders, tick_index);
        let order = linked_table::remove(&mut mut_tick_level.open_orders, order_id);
        assert!(order.owner == owner, EUnauthorizedCancel);
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
        let owner = account_owner(account_cap);
        assert!(contains(&pool.usr_open_orders, owner), EInvalidUser);
        let usr_open_order_ids = table::borrow_mut(&mut pool.usr_open_orders, owner);
        let mut canceled_order_events = vector[];
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
                owner
            );
            if (is_bid) {
                let (_, balance_locked) = clob_math::unsafe_mul_round(order.quantity, order.price);
                custodian::unlock_balance(&mut pool.quote_custodian, owner, balance_locked);
            } else {
                custodian::unlock_balance(&mut pool.base_custodian, owner, order.quantity);
            };
            let canceled_order_event = AllOrdersCanceledComponent<BaseAsset, QuoteAsset> {
                client_order_id: order.client_order_id,
                order_id: order.order_id,
                is_bid: order.is_bid,
                owner: order.owner,
                original_quantity: order.original_quantity,
                base_asset_quantity_canceled: order.quantity,
                price: order.price
            };

            vector::push_back(&mut canceled_order_events, canceled_order_event);
        };

        if (!vector::is_empty(&canceled_order_events)) {
            event::emit(AllOrdersCanceled<BaseAsset, QuoteAsset> {
                pool_id,
                orders_canceled: canceled_order_events,
            });
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
        let owner = account_owner(account_cap);
        assert!(contains(&pool.usr_open_orders, owner), 0);
        let mut tick_index: u64 = 0;
        let mut tick_price: u64 = 0;
        let n_order = vector::length(&order_ids);
        let mut i_order = 0;
        let usr_open_orders = borrow_mut(&mut pool.usr_open_orders, owner);
        let mut canceled_order_events = vector[];

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
                owner
            );
            if (is_bid) {
                let (_is_round_down, balance_locked) = clob_math::unsafe_mul_round(order.quantity, order.price);
                custodian::unlock_balance(&mut pool.quote_custodian, owner, balance_locked);
            } else {
                custodian::unlock_balance(&mut pool.base_custodian, owner, order.quantity);
            };
            let canceled_order_event = AllOrdersCanceledComponent<BaseAsset, QuoteAsset> {
                client_order_id: order.client_order_id,
                order_id: order.order_id,
                is_bid: order.is_bid,
                owner: order.owner,
                original_quantity: order.original_quantity,
                base_asset_quantity_canceled: order.quantity,
                price: order.price
            };
            vector::push_back(&mut canceled_order_events, canceled_order_event);

            i_order = i_order + 1;
        };

        if (!vector::is_empty(&canceled_order_events)) {
            event::emit(AllOrdersCanceled<BaseAsset, QuoteAsset> {
                pool_id,
                orders_canceled: canceled_order_events,
            });
        };
    }

    /// Clean up expired orders
    /// Note that this function can reduce gas cost if orders
    /// with the same price are grouped together in the vector because we would not need the computation to find the tick_index.
    /// For example, if we have the following order_id to price mapping, {0: 100., 1: 200., 2: 100., 3: 200.}.
    /// Grouping order_ids like [0, 2, 1, 3] would make it the most gas efficient.
    /// Order owners should be the owner addresses from the account capacities which placed the orders,
    /// and they should correspond to the order IDs one by one.
    public fun clean_up_expired_orders<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        clock: &Clock,
        order_ids: vector<u64>,
        order_owners: vector<address>
    ) {
        let pool_id = *object::uid_as_inner(&pool.id);
        let now = clock::timestamp_ms(clock);
        let n_order = vector::length(&order_ids);
        assert!(n_order == vector::length(&order_owners), ENotEqual);
        let mut i_order = 0;
        let mut tick_index: u64 = 0;
        let mut tick_price: u64 = 0;
        let mut canceled_order_events = vector[];
        while (i_order < n_order) {
            let order_id = *vector::borrow(&order_ids, i_order);
            let owner = *vector::borrow(&order_owners, i_order);
            if (!table::contains(&pool.usr_open_orders, owner)) { continue };
            let usr_open_orders = borrow_mut(&mut pool.usr_open_orders, owner);
            if (!linked_table::contains(usr_open_orders, order_id)) { continue };
            let new_tick_price = *linked_table::borrow(usr_open_orders, order_id);
            let is_bid = order_is_bid(order_id);
            let open_orders = if (is_bid) { &mut pool.bids } else { &mut pool.asks };
            if (new_tick_price != tick_price) {
                tick_price = new_tick_price;
                let (tick_exists, new_tick_index) = find_leaf(
                    open_orders,
                    tick_price
                );
                assert!(tick_exists, EInvalidTickPrice);
                tick_index = new_tick_index;
            };
            let order = remove_order(open_orders, usr_open_orders, tick_index, order_id, owner);
            assert!(order.expire_timestamp < now, EInvalidExpireTimestamp);
            if (is_bid) {
                let (_is_round_down, balance_locked) = clob_math::unsafe_mul_round(order.quantity, order.price);
                custodian::unlock_balance(&mut pool.quote_custodian, owner, balance_locked);
            } else {
                custodian::unlock_balance(&mut pool.base_custodian, owner, order.quantity);
            };
            let canceled_order_event = AllOrdersCanceledComponent<BaseAsset, QuoteAsset> {
                client_order_id: order.client_order_id,
                order_id: order.order_id,
                is_bid: order.is_bid,
                owner: order.owner,
                original_quantity: order.original_quantity,
                base_asset_quantity_canceled: order.quantity,
                price: order.price
            };
            vector::push_back(&mut canceled_order_events, canceled_order_event);

            i_order = i_order + 1;
        };

        if (!vector::is_empty(&canceled_order_events)) {
            event::emit(AllOrdersCanceled<BaseAsset, QuoteAsset> {
                pool_id,
                orders_canceled: canceled_order_events,
            });
        };
    }

    public fun list_open_orders<BaseAsset, QuoteAsset>(
        pool: &Pool<BaseAsset, QuoteAsset>,
        account_cap: &AccountCap
    ): vector<Order> {
        let owner = account_owner(account_cap);
        let mut open_orders = vector::empty<Order>();
        if (!usr_open_orders_exist(pool, owner)) {
            return open_orders
        };
        let usr_open_order_ids = table::borrow(&pool.usr_open_orders, owner);
        let mut order_id = linked_table::front(usr_open_order_ids);
        while (!option::is_none(order_id)) {
            let order_price = *linked_table::borrow(usr_open_order_ids, *option::borrow(order_id));
            let tick_level =
                if (order_is_bid(*option::borrow(order_id))) borrow_leaf_by_key(&pool.bids, order_price)
                else borrow_leaf_by_key(&pool.asks, order_price);
            let order = linked_table::borrow(&tick_level.open_orders, *option::borrow(order_id));
            vector::push_back(&mut open_orders, Order {
                order_id: order.order_id,
                client_order_id: order.client_order_id,
                price: order.price,
                original_quantity: order.original_quantity,
                quantity: order.quantity,
                is_bid: order.is_bid,
                owner: order.owner,
                expire_timestamp: order.expire_timestamp,
                self_matching_prevention: order.self_matching_prevention
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
        let owner = account_owner(account_cap);
        let (base_avail, base_locked) = custodian::account_balance(&pool.base_custodian, owner);
        let (quote_avail, quote_locked) = custodian::account_balance(&pool.quote_custodian, owner);
        (base_avail, base_locked, quote_avail, quote_locked)
    }

    /// Query the market price of order book
    /// returns (best_bid_price, best_ask_price) if there exists
    /// bid/ask order in the order book, otherwise returns None
    public fun get_market_price<BaseAsset, QuoteAsset>(
        pool: &Pool<BaseAsset, QuoteAsset>
    ): (Option<u64>, Option<u64>){
        let bid_price = if (!critbit::is_empty(&pool.bids)) {
            let (result, _) = critbit::max_leaf(&pool.bids);
            option::some<u64>(result)
        } else {
            option::none<u64>()
        };
        let ask_price = if (!critbit::is_empty(&pool.asks)) {
            let (result, _) = critbit::min_leaf(&pool.asks);
            option::some<u64>(result)
        } else {
            option::none<u64>()
        };
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
        let mut price_vec = vector::empty<u64>();
        let mut depth_vec = vector::empty<u64>();
        if (critbit::is_empty(&pool.bids)) { return (price_vec, depth_vec) };
        let (price_low_, _) = critbit::min_leaf(&pool.bids);
        let (price_high_, _) = critbit::max_leaf(&pool.bids);

        // If price_low is greater than the higest element in the tree, we return empty
        if (price_low > price_high_) {
            return (price_vec, depth_vec)
        };

        if (price_low < price_low_) price_low = price_low_;
        if (price_high > price_high_) price_high = price_high_;
        price_low = critbit::find_closest_key(&pool.bids, price_low);
        price_high = critbit::find_closest_key(&pool.bids, price_high);
        while (price_low <= price_high) {
            let depth = get_level2_book_status(
                &pool.bids,
                price_low,
                clock::timestamp_ms(clock)
            );
            if (depth != 0) {
                vector::push_back(&mut price_vec, price_low);
                vector::push_back(&mut depth_vec, depth);
            };
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
        let mut price_vec = vector::empty<u64>();
        let mut depth_vec = vector::empty<u64>();
        if (critbit::is_empty(&pool.asks)) { return (price_vec, depth_vec) };
        let (price_low_, _) = critbit::min_leaf(&pool.asks);

        // Price_high is less than the lowest leaf in the tree then we return an empty array
        if (price_high < price_low_) {
            return (price_vec, depth_vec)
        };

        if (price_low < price_low_) price_low = price_low_;
        let (price_high_, _) = critbit::max_leaf(&pool.asks);
        if (price_high > price_high_) price_high = price_high_;
        price_low = critbit::find_closest_key(&pool.asks, price_low);
        price_high = critbit::find_closest_key(&pool.asks, price_high);
        while (price_low <= price_high) {
            let depth = get_level2_book_status(
                &pool.asks,
                price_low,
                clock::timestamp_ms(clock)
            );
            if (depth != 0) {
                vector::push_back(&mut price_vec, price_low);
                vector::push_back(&mut depth_vec, depth);
            };
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
        let owner = account_owner(account_cap);
        assert!(table::contains(&pool.usr_open_orders, owner), EInvalidUser);
        let usr_open_order_ids = table::borrow(&pool.usr_open_orders, owner);
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

    fun matched_order_metadata<BaseAsset, QuoteAsset>(
        pool_id: ID,
        taker_address: address,
        order: &Order,
        base_asset_quantity_filled: u64,
        taker_commission: u64,
        maker_rebates: u64
    ): MatchedOrderMetadata<BaseAsset, QuoteAsset>{
        MatchedOrderMetadata<BaseAsset, QuoteAsset> {
            pool_id,
            order_id: order.order_id,
            is_bid: order.is_bid,
            taker_address,
            maker_address: order.owner,
            base_asset_quantity_filled,
            price: order.price,
            taker_commission,
            maker_rebates
        }
    }

    public fun matched_order_metadata_info<BaseAsset, QuoteAsset>(
        matched_order_metadata: &MatchedOrderMetadata<BaseAsset, QuoteAsset>
    ) : ( ID, u64, bool, address, address, u64, u64, u64, u64) {
        (
            matched_order_metadata.pool_id,
            matched_order_metadata.order_id,
            matched_order_metadata.is_bid,
            matched_order_metadata.taker_address,
            matched_order_metadata.maker_address,
            matched_order_metadata.base_asset_quantity_filled,
            matched_order_metadata.price,
            matched_order_metadata.taker_commission,
            matched_order_metadata.maker_rebates
        )
    }

    // Methods for accessing pool data, used by the order_query package
    public fun asks<BaseAsset, QuoteAsset>(pool: &Pool<BaseAsset, QuoteAsset>): &CritbitTree<TickLevel> {
        &pool.asks
    }

    public fun bids<BaseAsset, QuoteAsset>(pool: &Pool<BaseAsset, QuoteAsset>): &CritbitTree<TickLevel> {
        &pool.bids
    }

    public fun tick_size<BaseAsset, QuoteAsset>(pool: &Pool<BaseAsset, QuoteAsset>): u64 {
        pool.tick_size
    }

    public fun maker_rebate_rate<BaseAsset, QuoteAsset>(pool: &Pool<BaseAsset, QuoteAsset>): u64 {
        pool.maker_rebate_rate
    }

    public fun taker_fee_rate<BaseAsset, QuoteAsset>(pool: &Pool<BaseAsset, QuoteAsset>): u64 {
        pool.taker_fee_rate
    }

    public fun pool_size<BaseAsset, QuoteAsset>(pool: &Pool<BaseAsset, QuoteAsset>): u64 {
        critbit::size(&pool.asks) + critbit::size(&pool.bids)
    }

    public fun open_orders(tick_level: &TickLevel): &LinkedTable<u64, Order> {
        &tick_level.open_orders
    }

    // Order Accessors

    public fun order_id(order: &Order): u64 {
        order.order_id
    }

    public fun tick_level(order: &Order): u64 {
        order.price
    }

    public fun original_quantity(order: &Order): u64 {
        order.original_quantity
    }

    public fun quantity(order: &Order): u64 {
        order.quantity
    }

    public fun is_bid(order: &Order): bool {
        order.is_bid
    }

    public fun owner(order: &Order): address {
        order.owner
    }

    public fun expire_timestamp(order: &Order): u64 {
        order.expire_timestamp
    }

    public fun quote_asset_trading_fees_value<BaseAsset, QuoteAsset>(pool: &Pool<BaseAsset, QuoteAsset>): u64 {
        balance::value(&pool.quote_asset_trading_fees)
    }

    public(package) fun clone_order(order: &Order): Order {
        Order {
            order_id: order.order_id,
            client_order_id: order.client_order_id,
            price: order.price,
            original_quantity: order.original_quantity,
            quantity: order.quantity,
            is_bid: order.is_bid,
            owner: order.owner,
            expire_timestamp: order.expire_timestamp,
            self_matching_prevention: order.self_matching_prevention
        }
    }

    // Note that open orders and quotes can be directly accessed by loading in the entire Pool.

    #[test_only] use sui::coin::mint_for_testing;

    #[test_only] use sui::test_scenario::{Self, Scenario};

    #[test_only] const E_NULL: u64 = 0;

    #[test_only] const CLIENT_ID_ALICE: u64 = 0;
    #[test_only] const CLIENT_ID_BOB: u64 = 1;

    #[test_only] public struct USD {}

    #[test_only]
    public fun setup_test_with_tick_min(
        taker_fee_rate: u64,
        maker_rebate_rate: u64,
        // tick size with scaling
        tick_size: u64,
        min_size: u64,
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
                min_size,
                balance::create_for_testing(FEE_AMOUNT_FOR_CREATE_POOL),
                test_scenario::ctx(scenario)
            );
        };
    }

    // Test wrapped pool struct
    #[test_only]
    public struct WrappedPool<phantom BaseAsset, phantom QuoteAsset> has key, store {
        id: UID,
        pool: Pool<BaseAsset, QuoteAsset>,
    }

    #[test_only]
    public fun borrow_mut_pool<BaseAsset, QuoteAsset>(
        wpool: &mut WrappedPool<BaseAsset, QuoteAsset>
    ): &mut Pool<BaseAsset, QuoteAsset> {
        &mut wpool.pool
    }

    #[test_only]
    public fun setup_test_with_tick_min_and_wrapped_pool(
        taker_fee_rate: u64,
        maker_rebate_rate: u64,
        // tick size with scaling
        tick_size: u64,
        min_size: u64,
        scenario: &mut Scenario,
        sender: address,
    ) {
        test_scenario::next_tx(scenario, sender);
        {
            clock::share_for_testing(clock::create_for_testing(test_scenario::ctx(scenario)));
        };

        test_scenario::next_tx(scenario, sender);
        {
            let (pool, pool_owner_cap) = create_pool_with_return_<SUI, USD>(
                taker_fee_rate,
                maker_rebate_rate,
                tick_size,
                min_size,
                balance::create_for_testing(FEE_AMOUNT_FOR_CREATE_POOL),
                test_scenario::ctx(scenario)
            );
            transfer::share_object(WrappedPool {
                id: object::new(test_scenario::ctx(scenario)),
                pool
            });
            delete_pool_owner_cap(pool_owner_cap);
        };
    }

    #[test_only]
    public fun setup_test(
        taker_fee_rate: u64,
        maker_rebate_rate: u64,
        scenario: &mut Scenario,
        sender: address,
    ) {
        setup_test_with_tick_min(
            taker_fee_rate,
            maker_rebate_rate,
            1 * FLOAT_SCALING,
            1,
            scenario,
            sender,
        );
    }

    #[test_only]
    public fun setup_test_wrapped_pool(
        taker_fee_rate: u64,
        maker_rebate_rate: u64,
        scenario: &mut Scenario,
        sender: address,
    ) {
        setup_test_with_tick_min_and_wrapped_pool(
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
    public fun order_id_for_test(
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
        pool: &Pool<BaseAsset, QuoteAsset>
    ): (&Custodian<BaseAsset>, &Custodian<QuoteAsset>) {
        (&pool.base_custodian, &pool.quote_custodian)
    }

    #[test_only]
    public fun test_match_bid<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        account_cap: &AccountCap,
        client_order_id: u64,
        quantity: u64,
        price_limit: u64, // upper price limit if bid, lower price limit if ask, inclusive
        current_timestamp: u64,
    ): (u64, u64) {
        let quote_quantity_original = 1 << 63;
        let (base_balance_filled, quote_balance_left, _matched_order_metadata) = match_bid(
            pool,
            account_cap,
            client_order_id,
            quantity,
            price_limit,
            current_timestamp,
            balance::create_for_testing<QuoteAsset>(quote_quantity_original),
            false,
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
        account_cap: &AccountCap,
        client_order_id: u64,
        quantity: u64,
        price_limit: u64, // upper price limit if bid, lower price limit if ask, inclusive
        current_timestamp: u64,
    ): (u64, u64) {
        let quote_quantity_original = 1 << 63;
        let (base_balance_filled, quote_balance_left, _matched_order_metadata) = match_bid_with_quote_quantity(
            pool,
            account_cap,
            client_order_id,
            quantity,
            price_limit,
            current_timestamp,
            balance::create_for_testing<QuoteAsset>(quote_quantity_original),
            false
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
        account_cap: &AccountCap,
        client_order_id: u64,
        quantity: u64,
        price_limit: u64, // upper price limit if bid, lower price limit if ask, inclusive
        current_timestamp: u64,
    ): (u64, u64) {
        let (base_balance_left, quote_balance_filled, _matched_order_metadata) = match_ask(
            pool,
            account_cap,
            client_order_id,
            price_limit,
            current_timestamp,
            balance::create_for_testing<BaseAsset>(quantity),
            false
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
        client_order_id: u64,
        price: u64,
        original_quantity: u64,
        quantity: u64,
        is_bid: bool,
        self_matching_prevention: u8,
        account_cap: &AccountCap,
        ctx: &mut TxContext
    ) {
        inject_limit_order(pool,
            client_order_id, price, original_quantity, quantity, is_bid, self_matching_prevention, TIMESTAMP_INF, account_cap, ctx);
    }

    #[test_only]
    public fun test_inject_limit_order_with_expiration<BaseAsset, QuoteAsset>(
        pool: &mut Pool<BaseAsset, QuoteAsset>,
        client_order_id: u64,
        price: u64,
        original_quantity: u64,
        quantity: u64,
        is_bid: bool,
        self_matching_prevention: u8,
        expire_timestamp: u64,
        account_cap: &AccountCap,
        ctx: &mut TxContext
    ) {
        inject_limit_order(pool,
            client_order_id, price, original_quantity, quantity, is_bid, self_matching_prevention, expire_timestamp, account_cap, ctx);
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
        owner: address
    ): &LinkedTable<u64, u64> {
        assert!(contains(&pool.usr_open_orders, owner), 0);
        table::borrow(&pool.usr_open_orders, owner)
    }

    #[test_only]
    public fun test_construct_order(sequence_id: u64, client_order_id: u64, price: u64, original_quantity: u64, quantity: u64, is_bid: bool, owner: address): Order {
        Order {
            order_id: order_id_for_test(sequence_id, is_bid),
            client_order_id,
            price,
            original_quantity,
            quantity,
            is_bid,
            owner,
            expire_timestamp: TIMESTAMP_INF,
            self_matching_prevention: PREVENT_SELF_MATCHING_DEFAULT
        }
    }

    #[test_only]
    public fun test_construct_order_with_expiration(
        sequence_id: u64,
        client_order_id: u64,
        price: u64,
        original_quantity: u64,
        quantity: u64,
        is_bid: bool,
        owner: address,
        expire_timestamp: u64
    ): Order {
        Order {
            order_id: order_id_for_test(sequence_id, is_bid),
            client_order_id,
            price,
            original_quantity,
            quantity,
            is_bid,
            owner,
            expire_timestamp,
            self_matching_prevention: PREVENT_SELF_MATCHING_DEFAULT
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
        owner: address,
    ): Order {
        let order;
        if (is_bid) {
            order = remove_order(
                &mut pool.bids,
                borrow_mut(&mut pool.usr_open_orders, owner),
                tick_index,
                order_id_for_test(sequence_id, is_bid),
                owner
            )
        } else {
            order = remove_order(
                &mut pool.asks,
                borrow_mut(&mut pool.usr_open_orders, owner),
                tick_index,
                order_id_for_test(sequence_id, is_bid),
                owner
            )
        };
        order
    }

    #[test]
    #[expected_failure(abort_code = EInvalidRestriction)]
    fun test_place_limit_order_with_invalid_restrictions_() {
        let owner: address = @0xAAAA;
        let alice: address = @0xBBBB;
        let mut test = test_scenario::begin(owner);
        test_scenario::next_tx(&mut test, owner);
        {
            setup_test(0, 0, &mut test, owner);
        };
        test_scenario::next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(
                alice,
                test_scenario::ctx(&mut test)
            );
        };
        test_scenario::next_tx(&mut test, alice);
        {
            let mut pool = test_scenario::take_shared<Pool<SUI, USD>>(&test);
            let clock = test_scenario::take_shared<Clock>(&test);
            let account_cap = test_scenario::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            custodian::deposit(
                &mut pool.base_custodian,
                mint_for_testing<SUI>(1000 * 100000000, test_scenario::ctx(&mut test)),
                account_cap_user
            );
            custodian::deposit(
                &mut pool.quote_custodian,
                mint_for_testing<USD>(10000 * 100000000, test_scenario::ctx(&mut test)),
                account_cap_user
            );
            place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                5 * FLOAT_SCALING,
                200 * 100000000,
                PREVENT_SELF_MATCHING_DEFAULT,
                true,
                TIMESTAMP_INF,
                5,
                &clock,
                &account_cap,
                test_scenario::ctx(&mut test)
            );
            test_scenario::return_shared(pool);
            test_scenario::return_shared(clock);
            test_scenario::return_to_address<AccountCap>(alice, account_cap);
        };

        test_scenario::end(test);
    }

    #[test]
    #[expected_failure(abort_code = EOrderCannotBeFullyFilled)]
    fun test_place_limit_order_with_restrictions_FILL_OR_KILL_() {
        let owner: address = @0xAAAA;
        let alice: address = @0xBBBB;
        let bob: address = @0xCCCC;
        let mut test = test_scenario::begin(owner);
        test_scenario::next_tx(&mut test, owner);
        {
            setup_test(0, 0, &mut test, owner);
        };
        test_scenario::next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(
                alice,
                test_scenario::ctx(&mut test)
            );
        };
        test_scenario::next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(
                bob,
                test_scenario::ctx(&mut test)
            );
        };
        test_scenario::next_tx(&mut test, alice);
        {
            let mut pool = test_scenario::take_shared<Pool<SUI, USD>>(&test);
            let clock = test_scenario::take_shared<Clock>(&test);
            let account_cap = test_scenario::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            custodian::deposit(
                &mut pool.base_custodian,
                mint_for_testing<SUI>(1000 * 100000000, test_scenario::ctx(&mut test)),
                account_cap_user
            );
            custodian::deposit(
                &mut pool.quote_custodian,
                mint_for_testing<USD>(10000 * 100000000, test_scenario::ctx(&mut test)),
                account_cap_user
            );
            place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                5 * FLOAT_SCALING,
                200 * 100000000,
                PREVENT_SELF_MATCHING_DEFAULT,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                test_scenario::ctx(&mut test)
            );
            place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                4 * FLOAT_SCALING,
                200 * 100000000,
                PREVENT_SELF_MATCHING_DEFAULT,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                test_scenario::ctx(&mut test)
            );
            place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                4 * FLOAT_SCALING,
                200 * 100000000,
                PREVENT_SELF_MATCHING_DEFAULT,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                test_scenario::ctx(&mut test)
            );
            place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                10 * FLOAT_SCALING,
                1000 * 100000000,
                PREVENT_SELF_MATCHING_DEFAULT,
                false,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                test_scenario::ctx(&mut test)
            );
            let (next_bid_order_id, next_ask_order_id, _, _) = get_pool_stat(&pool);
            assert!(next_bid_order_id == order_id_for_test(3, true), 0);
            assert!(next_ask_order_id == order_id_for_test(1, false), 0);
            custodian::assert_user_balance<USD>(
                &pool.quote_custodian,
                account_cap_user,
                7400 * 100000000,
                2600 * 100000000
            );
            custodian::assert_user_balance<SUI>(&pool.base_custodian, account_cap_user, 0, 1000 * 100000000);
            test_scenario::return_shared(pool);
            test_scenario::return_shared(clock);
            test_scenario::return_to_address<AccountCap>(alice, account_cap);
        };

        test_scenario::next_tx(&mut test, bob);
        {
            let mut pool = test_scenario::take_shared<Pool<SUI, USD>>(&test);
            let clock = test_scenario::take_shared<Clock>(&test);
            let account_cap = test_scenario::take_from_address<AccountCap>(&test, bob);
            let account_cap_user = account_owner(&account_cap);
            custodian::deposit(
                &mut pool.base_custodian,
                mint_for_testing<SUI>(900 * 100000000, test_scenario::ctx(&mut test)),
                account_cap_user
            );
            custodian::assert_user_balance<SUI>(&pool.base_custodian, account_cap_user, 900 * 100000000, 0);
            place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_BOB,
                4 * FLOAT_SCALING,
                601 * 100000000,
                PREVENT_SELF_MATCHING_DEFAULT,
                false,
                TIMESTAMP_INF,
                FILL_OR_KILL,
                &clock,
                &account_cap,
                test_scenario::ctx(&mut test)
            );
            custodian::assert_user_balance<USD>(&pool.quote_custodian, account_cap_user, 900 * 100000000, 0);
            test_scenario::return_shared(pool);
            test_scenario::return_shared(clock);
            test_scenario::return_to_address<AccountCap>(bob, account_cap);
        };
        test_scenario::end(test);
    }

    #[test]
    #[expected_failure(abort_code = EOrderCannotBeFullyPassive)]
    fun test_place_limit_order_with_restrictions_E_ORDER_CANNOT_BE_FULLY_PASSIVE_() {
        let owner: address = @0xAAAA;
        let alice: address = @0xBBBB;
        let bob: address = @0xCCCC;
        let mut test = test_scenario::begin(owner);
        test_scenario::next_tx(&mut test, owner);
        {
            setup_test(0, 0, &mut test, owner);
        };
        test_scenario::next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(
                alice,
                test_scenario::ctx(&mut test)
            );
        };
        test_scenario::next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(
                bob,
                test_scenario::ctx(&mut test)
            );
        };
        test_scenario::next_tx(&mut test, alice);
        {
            let mut pool = test_scenario::take_shared<Pool<SUI, USD>>(&test);
            let clock = test_scenario::take_shared<Clock>(&test);
            let account_cap = test_scenario::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            custodian::deposit(
                &mut pool.base_custodian,
                mint_for_testing<SUI>(1000 * 100000000, test_scenario::ctx(&mut test)),
                account_cap_user
            );
            custodian::deposit(
                &mut pool.quote_custodian,
                mint_for_testing<USD>(10000 * 100000000, test_scenario::ctx(&mut test)),
                account_cap_user
            );
            place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                5 * FLOAT_SCALING,
                200 * 100000000,
                PREVENT_SELF_MATCHING_DEFAULT,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                test_scenario::ctx(&mut test)
            );
            place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                4 * FLOAT_SCALING,
                200 * 100000000,
                PREVENT_SELF_MATCHING_DEFAULT,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                test_scenario::ctx(&mut test)
            );
            place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                4 * FLOAT_SCALING,
                200 * 100000000,
                PREVENT_SELF_MATCHING_DEFAULT,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                test_scenario::ctx(&mut test)
            );
            place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                10 * FLOAT_SCALING,
                1000 * 100000000,
                PREVENT_SELF_MATCHING_DEFAULT,
                false,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                test_scenario::ctx(&mut test)
            );
            let (next_bid_order_id, next_ask_order_id, _, _) = get_pool_stat(&pool);
            assert!(next_bid_order_id == order_id_for_test(3, true), 0);
            assert!(next_ask_order_id == order_id_for_test(1, false), 0);
            custodian::assert_user_balance<USD>(
                &pool.quote_custodian,
                account_cap_user,
                7400 * 100000000,
                2600 * 100000000
            );
            custodian::assert_user_balance<SUI>(&pool.base_custodian, account_cap_user, 0, 1000 * 100000000);
            test_scenario::return_shared(pool);
            test_scenario::return_shared(clock);
            test_scenario::return_to_address<AccountCap>(alice, account_cap);
        };

        test_scenario::next_tx(&mut test, bob);
        {
            let mut pool = test_scenario::take_shared<Pool<SUI, USD>>(&test);
            let clock = test_scenario::take_shared<Clock>(&test);
            let account_cap = test_scenario::take_from_address<AccountCap>(&test, bob);
            let account_cap_user = account_owner(&account_cap);
            custodian::deposit(
                &mut pool.base_custodian,
                mint_for_testing<SUI>(900 * 100000000, test_scenario::ctx(&mut test)),
                account_cap_user
            );
            custodian::assert_user_balance<SUI>(&pool.base_custodian, account_cap_user, 900 * 100000000, 0);
            place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_BOB,
                4 * FLOAT_SCALING,
                601 * 100000000,
                PREVENT_SELF_MATCHING_DEFAULT,
                false,
                TIMESTAMP_INF,
                POST_OR_ABORT,
                &clock,
                &account_cap,
                test_scenario::ctx(&mut test)
            );
            custodian::assert_user_balance<SUI>(&pool.base_custodian, account_cap_user, 900 * 100000000, 0);
            test_scenario::return_shared(pool);
            test_scenario::return_shared(clock);
            test_scenario::return_to_address<AccountCap>(bob, account_cap);
        };
        test_scenario::end(test);
    }

    #[test]
    fun test_place_limit_order_with_restrictions_IMMEDIATE_OR_CANCEL() {
        let owner: address = @0xAAAA;
        let alice: address = @0xBBBB;
        let bob: address = @0xCCCC;
        let mut test = test_scenario::begin(owner);
        test_scenario::next_tx(&mut test, owner);
        {
            setup_test(0, 0, &mut test, owner);
        };
        test_scenario::next_tx(&mut test, alice);
        {
            mint_account_cap_transfer(
                alice,
                test_scenario::ctx(&mut test)
            );
        };
        test_scenario::next_tx(&mut test, bob);
        {
            mint_account_cap_transfer(
                bob,
                test_scenario::ctx(&mut test)
            );
        };
        test_scenario::next_tx(&mut test, alice);
        {
            let mut pool = test_scenario::take_shared<Pool<SUI, USD>>(&test);
            let clock = test_scenario::take_shared<Clock>(&test);
            let account_cap = test_scenario::take_from_address<AccountCap>(&test, alice);
            let account_cap_user = account_owner(&account_cap);
            custodian::deposit(
                &mut pool.base_custodian,
                mint_for_testing<SUI>(1000 * 100000000, test_scenario::ctx(&mut test)),
                account_cap_user
            );
            custodian::deposit(
                &mut pool.quote_custodian,
                mint_for_testing<USD>(10000 * 100000000, test_scenario::ctx(&mut test)),
                account_cap_user
            );
            place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                5 * FLOAT_SCALING,
                200 * 100000000,
                PREVENT_SELF_MATCHING_DEFAULT,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                test_scenario::ctx(&mut test)
            );
            place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                4 * FLOAT_SCALING,
                200 * 100000000,
                PREVENT_SELF_MATCHING_DEFAULT,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                test_scenario::ctx(&mut test)
            );
            place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                4 * FLOAT_SCALING,
                200 * 100000000,
                PREVENT_SELF_MATCHING_DEFAULT,
                true,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                test_scenario::ctx(&mut test)
            );

            let (base_filled, quote_filled, maker_injected, maker_order_id) = place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                10 * FLOAT_SCALING,
                1000 * 100000000,
                PREVENT_SELF_MATCHING_DEFAULT,
                false,
                TIMESTAMP_INF,
                0,
                &clock,
                &account_cap,
                test_scenario::ctx(&mut test)
            );
            assert!(base_filled == 0, E_NULL);
            assert!(quote_filled == 0, E_NULL);
            assert!(maker_injected, E_NULL);
            assert!(maker_order_id == order_id_for_test(0, false), E_NULL);

            let (next_bid_order_id, next_ask_order_id, _, _) = get_pool_stat(&pool);
            assert!(next_bid_order_id == order_id_for_test(3, true), 0);
            assert!(next_ask_order_id == order_id_for_test(1, false), 0);
            custodian::assert_user_balance<USD>(
                &pool.quote_custodian,
                account_cap_user,
                7400 * 100000000,
                2600 * 100000000
            );
            custodian::assert_user_balance<SUI>(&pool.base_custodian, account_cap_user, 0, 1000 * 100000000);
            test_scenario::return_shared(pool);
            test_scenario::return_shared(clock);
            test_scenario::return_to_address<AccountCap>(alice, account_cap);
        };

        test_scenario::next_tx(&mut test, bob);
        {
            let mut pool = test_scenario::take_shared<Pool<SUI, USD>>(&test);
            let clock = test_scenario::take_shared<Clock>(&test);
            let account_cap = test_scenario::take_from_address<AccountCap>(&test, bob);
            let account_cap_user = account_owner(&account_cap);
            custodian::deposit(
                &mut pool.base_custodian,
                mint_for_testing<SUI>(900 * 100000000, test_scenario::ctx(&mut test)),
                account_cap_user
            );
            custodian::assert_user_balance<SUI>(&pool.base_custodian, account_cap_user, 900 * 100000000, 0);

            let (base_filled, quote_filled, maker_injected, _) = place_limit_order<SUI, USD>(
                &mut pool,
                CLIENT_ID_ALICE,
                4 * FLOAT_SCALING,
                800 * 100000000,
                PREVENT_SELF_MATCHING_DEFAULT,
                false,
                TIMESTAMP_INF,
                IMMEDIATE_OR_CANCEL,
                &clock,
                &account_cap,
                test_scenario::ctx(&mut test)
            );
            assert!(base_filled == 600 * 100000000, E_NULL);
            assert!(quote_filled == 2600 * 100000000, E_NULL);
            assert!(!maker_injected, E_NULL);

            custodian::assert_user_balance<SUI>(&pool.base_custodian, account_cap_user, 300 * 100000000, 0);
            {
                let (_, _, bids, _) = get_pool_stat(&pool);
                check_empty_tick_level(bids, 4 * FLOAT_SCALING);
            };
            test_scenario::return_shared(pool);
            test_scenario::return_shared(clock);
            test_scenario::return_to_address<AccountCap>(bob, account_cap);
        };
        test_scenario::end(test);
    }

    #[test]
    #[expected_failure(abort_code = EInvalidPair)]
    fun test_create_pool_invalid_pair() {
        let owner: address = @0xAAAA;
        let mut test = test_scenario::begin(owner);
        test_scenario::next_tx(&mut test, owner);
        {
            setup_test(0, 0, &mut test, owner);
        };
        // create pool which is already exist fail
        test_scenario::next_tx(&mut test, owner);
        {
            create_pool_<SUI, SUI>(
                REFERENCE_TAKER_FEE_RATE,
                REFERENCE_MAKER_REBATE_RATE,
                1 * FLOAT_SCALING,
                1,
                balance::create_for_testing(FEE_AMOUNT_FOR_CREATE_POOL),
                test_scenario::ctx(&mut test)
            );
        };
        test_scenario::end(test);
    }

    #[test]
    #[expected_failure(abort_code = EInvalidTickSizeMinSize)]
    fun test_create_pool_invalid_tick_size_min_size() {
        let owner: address = @0xAAAA;
        let mut test = test_scenario::begin(owner);
        test_scenario::next_tx(&mut test, owner);
        {
            setup_test(0, 0, &mut test, owner);
        };
        // create pool which is already exist fail
        test_scenario::next_tx(&mut test, owner);
        {
            create_pool_<SUI, SUI>(
                REFERENCE_TAKER_FEE_RATE,
                REFERENCE_MAKER_REBATE_RATE,
                100_000,
                5,
                balance::create_for_testing(FEE_AMOUNT_FOR_CREATE_POOL),
            test_scenario::ctx(&mut test)
            );
        };
        test_scenario::end(test);
    }

    // Ensure that the custodian's locked balance matches the sum of all values for a given account
    // Assumption: custodian has only placed orders in the given pool--if they have orders in other pools, the locked balance will be too small
    #[test_only]
    public fun check_balance_invariants_for_account<BaseAsset, QuoteAsset>(
        account_cap: &AccountCap,
        quote_custodian: &Custodian<QuoteAsset>,
        base_custodian: &Custodian<BaseAsset>,
        pool: &Pool<BaseAsset, QuoteAsset>
    ) {
        let account_cap_user = custodian::account_owner(account_cap);
        let quote_account_locked_balance = custodian::account_locked_balance<QuoteAsset>(quote_custodian, account_cap_user);
        let base_account_locked_balance = custodian::account_locked_balance<BaseAsset>(base_custodian, account_cap_user);
        let usr_open_order_ids = table::borrow(&pool.usr_open_orders, account_cap_user);

        let mut quote_asset_amount = 0;
        let mut base_asset_amount = 0;
        let mut curr = linked_table::front(usr_open_order_ids);

        while (option::is_some(curr)) {
            let order_id = *option::borrow(curr);
            let order = get_order_status<BaseAsset, QuoteAsset>(pool, order_id, account_cap);
            let (_is_round_down, total_balance) = clob_math::unsafe_mul_round(order.price, order.quantity);
            if (order.is_bid) {
                quote_asset_amount = quote_asset_amount + total_balance;
            } else {
                // For base swaps we actually only need the order quantity
                base_asset_amount = base_asset_amount + order.quantity;
            };
            curr = linked_table::next(usr_open_order_ids, order_id);
        };
        assert!(quote_asset_amount == quote_account_locked_balance, 0);
        assert!(base_asset_amount == base_account_locked_balance, 0);
    }
}
