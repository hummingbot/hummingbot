// Copyright (c) Mysten Labs, Inc.
// SPDX-License-Identifier: Apache-2.0

module deepbook::custodian_v2 {
    use sui::balance::{Self, Balance, split};
    use sui::coin::{Self, Coin};
    use sui::table::{Self, Table};

    // <<<<<<<<<<<<<<<<<<<<<<<< Error codes <<<<<<<<<<<<<<<<<<<<<<<<
    #[test_only]
    const EUserBalanceDoesNotExist: u64 = 1;
    const EAdminAccountCapRequired: u64 = 2;
    // <<<<<<<<<<<<<<<<<<<<<<<< Error codes <<<<<<<<<<<<<<<<<<<<<<<<

    public struct Account<phantom T> has store {
        available_balance: Balance<T>,
        locked_balance: Balance<T>,
    }

    /// Capability granting permission to access an entry in `Custodian.account_balances`.
    /// Calling `mint_account_cap` creates an "admin account cap" such that id == owner with
    /// the permission to both access funds and create new `AccountCap`s.
    /// Calling `create_child_account_cap` creates a "child account cap" such that id != owner
    /// that can access funds, but cannot create new `AccountCap`s.
    public struct AccountCap has key, store {
        id: UID,
        /// The owner of this AccountCap. Note: this is
        /// derived from an object ID, not a user address
        owner: address
    }

    // Custodian for limit orders.
    public struct Custodian<phantom T> has key, store {
        id: UID,
        /// Map from the owner address of AccountCap object to an Account object
        account_balances: Table<address, Account<T>>,
    }

    /// Create an admin `AccountCap` that can be used across all DeepBook pools, and has
    /// the permission to create new `AccountCap`s that can access the same source of funds
    public(package) fun mint_account_cap(ctx: &mut TxContext): AccountCap {
        let id = object::new(ctx);
        let owner = object::uid_to_address(&id);
        AccountCap { id, owner }
    }

    /// Create a "child account cap" such that id != owner
    /// that can access funds, but cannot create new `AccountCap`s.
    public fun create_child_account_cap(admin_account_cap: &AccountCap, ctx: &mut TxContext): AccountCap {
        // Only the admin account cap can create new account caps
        assert!(object::uid_to_address(&admin_account_cap.id) == admin_account_cap.owner, EAdminAccountCapRequired);

        AccountCap {
            id: object::new(ctx),
            owner: admin_account_cap.owner
        }
    }

    /// Destroy the given `account_cap` object
    public fun delete_account_cap(account_cap: AccountCap) {
        let AccountCap { id, owner: _ } = account_cap;
        object::delete(id)
    }

    /// Return the owner of an AccountCap
    public fun account_owner(account_cap: &AccountCap): address {
        account_cap.owner
    }

    public(package) fun account_balance<Asset>(
        custodian: &Custodian<Asset>,
        owner: address
    ): (u64, u64) {
        // if custodian account is not created yet, directly return (0, 0) rather than abort
        if (!table::contains(&custodian.account_balances, owner)) {
            return (0, 0)
        };
        let account_balances = table::borrow(&custodian.account_balances, owner);
        let avail_balance = balance::value(&account_balances.available_balance);
        let locked_balance = balance::value(&account_balances.locked_balance);
        (avail_balance, locked_balance)
    }

    public(package) fun new<T>(ctx: &mut TxContext): Custodian<T> {
        Custodian<T> {
            id: object::new(ctx),
            account_balances: table::new(ctx),
        }
    }

    public(package) fun withdraw_asset<Asset>(
        custodian: &mut Custodian<Asset>,
        quantity: u64,
        account_cap: &AccountCap,
        ctx: &mut TxContext
    ): Coin<Asset> {
        coin::from_balance(decrease_user_available_balance<Asset>(custodian, account_cap, quantity), ctx)
    }

    public(package) fun increase_user_available_balance<T>(
        custodian: &mut Custodian<T>,
        owner: address,
        quantity: Balance<T>,
    ) {
        let account = borrow_mut_account_balance<T>(custodian, owner);
        balance::join(&mut account.available_balance, quantity);
    }

    public(package) fun decrease_user_available_balance<T>(
        custodian: &mut Custodian<T>,
        account_cap: &AccountCap,
        quantity: u64,
    ): Balance<T> {
        let account = borrow_mut_account_balance<T>(custodian, account_cap.owner);
        balance::split(&mut account.available_balance, quantity)
    }

    public(package) fun increase_user_locked_balance<T>(
        custodian: &mut Custodian<T>,
        account_cap: &AccountCap,
        quantity: Balance<T>,
    ) {
        let account = borrow_mut_account_balance<T>(custodian, account_cap.owner);
        balance::join(&mut account.locked_balance, quantity);
    }

    public(package) fun decrease_user_locked_balance<T>(
        custodian: &mut Custodian<T>,
        owner: address,
        quantity: u64,
    ): Balance<T> {
        let account = borrow_mut_account_balance<T>(custodian, owner);
        split(&mut account.locked_balance, quantity)
    }

    /// Move `quantity` from the unlocked balance of `user` to the locked balance of `user`
    public(package) fun lock_balance<T>(
        custodian: &mut Custodian<T>,
        account_cap: &AccountCap,
        quantity: u64,
    ) {
        let to_lock = decrease_user_available_balance(custodian, account_cap, quantity);
        increase_user_locked_balance(custodian, account_cap, to_lock);
    }

    /// Move `quantity` from the locked balance of `user` to the unlocked balance of `user`
    public(package) fun unlock_balance<T>(
        custodian: &mut Custodian<T>,
        owner: address,
        quantity: u64,
    ) {
        let locked_balance = decrease_user_locked_balance<T>(custodian, owner, quantity);
        increase_user_available_balance<T>(custodian, owner, locked_balance)
    }

    public(package) fun account_available_balance<T>(
        custodian: &Custodian<T>,
        owner: address,
    ): u64 {
        balance::value(&table::borrow(&custodian.account_balances, owner).available_balance)
    }

    public(package) fun account_locked_balance<T>(
        custodian: &Custodian<T>,
        owner: address,
    ): u64 {
        balance::value(&table::borrow(&custodian.account_balances, owner).locked_balance)
    }

    fun borrow_mut_account_balance<T>(
        custodian: &mut Custodian<T>,
        owner: address,
    ): &mut Account<T> {
        if (!table::contains(&custodian.account_balances, owner)) {
            table::add(
                &mut custodian.account_balances,
                owner,
                Account { available_balance: balance::zero(), locked_balance: balance::zero() }
            );
        };
        table::borrow_mut(&mut custodian.account_balances, owner)
    }

    #[test_only]
    fun borrow_account_balance<T>(
        custodian: &Custodian<T>,
        owner: address,
    ): &Account<T> {
        assert!(
            table::contains(&custodian.account_balances, owner),
            EUserBalanceDoesNotExist
        );
        table::borrow(&custodian.account_balances, owner)
    }

    #[test_only]
    use sui::test_scenario::{Self, Scenario, take_shared, take_from_sender, ctx};
    #[test_only]
    use sui::coin::{mint_for_testing};
    #[test_only]
    use sui::test_utils::{assert_eq, destroy};

    #[test_only]
    const ENull: u64 = 0;

    #[test_only]
    public struct USD {}

    #[test_only]
    public(package) fun assert_user_balance<T>(
        custodian: &Custodian<T>,
        owner: address,
        available_balance: u64,
        locked_balance: u64,
    ) {
        let user_balance = borrow_account_balance<T>(custodian, owner);
        assert!(balance::value(&user_balance.available_balance) == available_balance, ENull);
        assert!(balance::value(&user_balance.locked_balance) == locked_balance, ENull)
    }

    #[test_only]
    fun setup_test(
        scenario: &mut Scenario,
    ) {
        transfer::share_object<Custodian<USD>>(new<USD>(test_scenario::ctx(scenario)));
    }

    #[test_only]
    public(package) fun test_increase_user_available_balance<T>(
        custodian: &mut Custodian<T>,
        owner: address,
        quantity: u64,
    ) {
        increase_user_available_balance<T>(custodian, owner, balance::create_for_testing(quantity));
    }

    #[test_only]
    public(package) fun deposit<T>(
        custodian: &mut Custodian<T>,
        coin: Coin<T>,
        owner: address,
    ) {
        increase_user_available_balance<T>(custodian, owner, coin::into_balance(coin));
    }

    #[test]
    #[expected_failure(abort_code = EUserBalanceDoesNotExist)]
    fun test_user_balance_does_not_exist(){
        let owner: address = @0xAAAA;
        let bob: address = @0xBBBB;
        let mut test = test_scenario::begin(owner);
        test_scenario::next_tx(&mut test, owner);
        {
            setup_test(&mut test);
            transfer::public_transfer(mint_account_cap(ctx(&mut test)), bob);
        };
        test_scenario::next_tx(&mut test, bob);
        {
            let custodian = take_shared<Custodian<USD>>(&test);
            let account_cap = take_from_sender<AccountCap>(&test);
            let _ = borrow_account_balance(&custodian, bob);
            test_scenario::return_to_sender<AccountCap>(&test, account_cap);
            test_scenario::return_shared(custodian);

        };
        test_scenario::end(test);
    }

    #[test]
    fun test_account_balance() {
        let owner: address = @0xAAAA;
        let bob: address = @0xBBBB;
        let mut test = test_scenario::begin(owner);
        test_scenario::next_tx(&mut test, owner);
        {
            setup_test(&mut test);
            transfer::public_transfer(mint_account_cap(ctx(&mut test)), bob);
        };
        test_scenario::next_tx(&mut test, bob);
        {
            let custodian = take_shared<Custodian<USD>>(&test);
            let account_cap = take_from_sender<AccountCap>(&test);
            let (asset_available, asset_locked) = account_balance(&custodian, bob);
            assert_eq(asset_available, 0);
            assert_eq(asset_locked, 0);
            test_scenario::return_to_sender<AccountCap>(&test, account_cap);
            test_scenario::return_shared(custodian);

        };
        test_scenario::next_tx(&mut test, bob);
        {
            let mut custodian = take_shared<Custodian<USD>>(&test);
            let account_cap = take_from_sender<AccountCap>(&test);
            deposit(&mut custodian, mint_for_testing<USD>(10000, ctx(&mut test)), bob);
            let (asset_available, mut asset_locked) = account_balance(&custodian, bob);
            assert_eq(asset_available, 10000);
            assert_eq(asset_locked, 0);
            asset_locked = account_locked_balance(&custodian, bob);
            assert_eq(asset_locked, 0);
            test_scenario::return_to_sender<AccountCap>(&test, account_cap);
            test_scenario::return_shared(custodian);
        };
        test_scenario::end(test);
    }

    #[test]
    fun test_create_child_account_cap() {
        let mut ctx = tx_context::dummy();
        let admin_cap = mint_account_cap(&mut ctx);
        // check that we can duplicate child cap, and don't get another admin cap
        let child_cap = create_child_account_cap(&admin_cap, &mut ctx);
        assert_eq(child_cap.owner, admin_cap.owner);
        assert!(&child_cap.id != &admin_cap.id, 0);

        // check that both child and admin cap can access the funds
        let mut custodian = new<USD>(&mut ctx);
        increase_user_available_balance(&mut custodian, account_owner(&admin_cap), balance::create_for_testing(10000));
        let coin = decrease_user_available_balance(&mut custodian, &child_cap, 10000);

        destroy(admin_cap);
        destroy(child_cap);
        destroy(custodian);
        destroy(coin);
    }

    #[expected_failure(abort_code = EAdminAccountCapRequired)]
    #[test]
    fun test_cant_create_with_child() {
        // a child cap cannot create an account cap
        let mut ctx = tx_context::dummy();
        let admin_cap = mint_account_cap(&mut ctx);
        // check that we can duplicate child cap, and don't get another admin cap
        let child_cap1 = create_child_account_cap(&admin_cap, &mut ctx);
        let child_cap2 = create_child_account_cap(&child_cap1, &mut ctx); // should abort

        destroy(admin_cap);
        destroy(child_cap1);
        destroy(child_cap2);
    }
}
