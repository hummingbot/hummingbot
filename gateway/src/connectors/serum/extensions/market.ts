/*
Apache License Version 2.0

https://raw.githubusercontent.com/project-serum/serum-ts/master/LICENSE
 */

import { getFilteredProgramAccounts } from '@blockworks-foundation/mango-client';
import {
  getFeeTier,
  supportsSrmFeeDiscounts,
} from '@project-serum/serum/lib/fees';
import { DexInstructions } from '@project-serum/serum/lib/instructions';
import {
  _MARKET_STAT_LAYOUT_V1,
  getMintDecimals,
  MARKET_STATE_LAYOUT_V2,
  MarketOptions,
  OpenOrders,
  Order,
  Orderbook,
  OrderParams,
  OrderParamsAccounts,
  OrderParamsBase,
} from '@project-serum/serum/lib/market';
import {
  decodeEventQueue,
  decodeRequestQueue,
} from '@project-serum/serum/lib/queue';
import {
  closeAccount,
  initializeAccount,
  MSRM_DECIMALS,
  MSRM_MINT,
  SRM_DECIMALS,
  SRM_MINT,
  TOKEN_PROGRAM_ID,
  WRAPPED_SOL_MINT,
} from '@project-serum/serum/lib/token-instructions';
import { getLayoutVersion } from '@project-serum/serum/lib/tokens_and_markets';
import {
  Account,
  AccountInfo,
  Commitment,
  Connection,
  LAMPORTS_PER_SOL,
  PublicKey,
  SystemProgram,
  Transaction,
  TransactionInstruction,
  TransactionSignature,
} from '@solana/web3.js';
import BN from 'bn.js';
import { Buffer } from 'buffer';
import { promiseAllInBatches } from '../serum.helpers';
import { OriginalSerumMarket } from '../serum.types';

export class Market {
  private _decoded: any;
  private _baseSplTokenDecimals: number;
  private _quoteSplTokenDecimals: number;
  private _skipPreflight: boolean;
  private _commitment: Commitment;
  private _programId: PublicKey;
  private _openOrdersAccountsCache: {
    [publickKey: string]: { accounts: OpenOrders[]; ts: number };
  };
  protected _layoutOverride?: any;

  private _feeDiscountKeysCache: {
    [publicKey: string]: {
      accounts: Array<{
        balance: number;
        mint: PublicKey;
        pubkey: PublicKey;
        feeTier: number;
      }>;
      ts: number;
    };
  };

  constructor(
    decoded: any,
    baseMintDecimals: number,
    quoteMintDecimals: number,
    options: MarketOptions = {},
    programId: PublicKey,
    layoutOverride?: any
  ) {
    const { skipPreflight = false, commitment = 'recent' } = options;
    if (!decoded.accountFlags.initialized || !decoded.accountFlags.market) {
      throw new Error('Invalid market state');
    }
    this._decoded = decoded;
    this._baseSplTokenDecimals = baseMintDecimals;
    this._quoteSplTokenDecimals = quoteMintDecimals;
    this._skipPreflight = skipPreflight;
    this._commitment = commitment;
    this._programId = programId;
    this._openOrdersAccountsCache = {};
    this._feeDiscountKeysCache = {};
    this._layoutOverride = layoutOverride;
  }

  static getLayout(programId: PublicKey) {
    if (getLayoutVersion(programId) === 1) {
      return _MARKET_STAT_LAYOUT_V1;
    }
    return MARKET_STATE_LAYOUT_V2;
  }

  static async findAccountsByMints(
    connection: Connection,
    baseMintAddress: PublicKey,
    quoteMintAddress: PublicKey,
    programId: PublicKey
  ) {
    const filters = [
      {
        memcmp: {
          offset: this.getLayout(programId).offsetOf('baseMint'),
          bytes: baseMintAddress.toBase58(),
        },
      },
      {
        memcmp: {
          offset: Market.getLayout(programId).offsetOf('quoteMint'),
          bytes: quoteMintAddress.toBase58(),
        },
      },
    ];
    return getFilteredProgramAccounts(connection, programId, filters);
  }

  static async load(
    connection: Connection,
    address: PublicKey,
    options: MarketOptions = {},
    programId: PublicKey,
    layoutOverride?: any
  ) {
    const { owner, data } = throwIfNull(
      await connection.getAccountInfo(address),
      'Market not found'
    );
    if (!owner.equals(programId)) {
      throw new Error('Address not owned by program: ' + owner.toBase58());
    }
    const decoded = (layoutOverride ?? this.getLayout(programId)).decode(data);
    if (
      !decoded.accountFlags.initialized ||
      !decoded.accountFlags.market ||
      !decoded.ownAddress.equals(address)
    ) {
      throw new Error('Invalid market');
    }
    const [baseMintDecimals, quoteMintDecimals] = await Promise.all([
      getMintDecimals(connection, decoded.baseMint),
      getMintDecimals(connection, decoded.quoteMint),
    ]);

    return new Market(
      decoded,
      baseMintDecimals,
      quoteMintDecimals,
      options,
      programId,
      layoutOverride
    );
  }

  get programId(): PublicKey {
    return this._programId;
  }

  get address(): PublicKey {
    return this._decoded.ownAddress;
  }

  get publicKey(): PublicKey {
    return this.address;
  }

  get baseMintAddress(): PublicKey {
    return this._decoded.baseMint;
  }

  get quoteMintAddress(): PublicKey {
    return this._decoded.quoteMint;
  }

  get bidsAddress(): PublicKey {
    return this._decoded.bids;
  }

  get asksAddress(): PublicKey {
    return this._decoded.asks;
  }

  get decoded(): any {
    return this._decoded;
  }

  async loadBids(connection: Connection): Promise<Orderbook> {
    const { data } = throwIfNull(
      await connection.getAccountInfo(this._decoded.bids)
    );
    return Orderbook.decode(this as unknown as OriginalSerumMarket, data);
  }

  async loadAsks(connection: Connection): Promise<Orderbook> {
    const { data } = throwIfNull(
      await connection.getAccountInfo(this._decoded.asks)
    );
    return Orderbook.decode(this as unknown as OriginalSerumMarket, data);
  }

  async loadOrdersForOwner(
    connection: Connection,
    ownerAddress: PublicKey,
    cacheDurationMs = 0
  ): Promise<Order[]> {
    const [bids, asks, openOrdersAccounts] = await Promise.all([
      this.loadBids(connection),
      this.loadAsks(connection),
      this.findOpenOrdersAccountsForOwner(
        connection,
        ownerAddress,
        cacheDurationMs
      ),
    ]);
    return this.filterForOpenOrders(bids, asks, openOrdersAccounts);
  }

  filterForOpenOrders(
    bids: Orderbook,
    asks: Orderbook,
    openOrdersAccounts: OpenOrders[]
  ): Order[] {
    return [...bids, ...asks].filter((order) =>
      openOrdersAccounts.some((openOrders) =>
        order.openOrdersAddress.equals(openOrders.address)
      )
    );
  }

  async findBaseTokenAccountsForOwner(
    connection: Connection,
    ownerAddress: PublicKey,
    includeUnwrappedSol = false
  ): Promise<Array<{ pubkey: PublicKey; account: AccountInfo<Buffer> }>> {
    if (this.baseMintAddress.equals(WRAPPED_SOL_MINT) && includeUnwrappedSol) {
      const [wrapped, unwrapped] = await Promise.all([
        this.findBaseTokenAccountsForOwner(connection, ownerAddress, false),
        connection.getAccountInfo(ownerAddress),
      ]);
      if (unwrapped !== null) {
        return [{ pubkey: ownerAddress, account: unwrapped }, ...wrapped];
      }
      return wrapped;
    }
    return await this.getTokenAccountsByOwnerForMint(
      connection,
      ownerAddress,
      this.baseMintAddress
    );
  }

  async getTokenAccountsByOwnerForMint(
    connection: Connection,
    ownerAddress: PublicKey,
    mintAddress: PublicKey
  ): Promise<Array<{ pubkey: PublicKey; account: AccountInfo<Buffer> }>> {
    return (
      await connection.getTokenAccountsByOwner(ownerAddress, {
        mint: mintAddress,
      })
    ).value;
  }

  async findQuoteTokenAccountsForOwner(
    connection: Connection,
    ownerAddress: PublicKey,
    includeUnwrappedSol = false
  ): Promise<{ pubkey: PublicKey; account: AccountInfo<Buffer> }[]> {
    if (this.quoteMintAddress.equals(WRAPPED_SOL_MINT) && includeUnwrappedSol) {
      const [wrapped, unwrapped] = await Promise.all([
        this.findQuoteTokenAccountsForOwner(connection, ownerAddress, false),
        connection.getAccountInfo(ownerAddress),
      ]);
      if (unwrapped !== null) {
        return [{ pubkey: ownerAddress, account: unwrapped }, ...wrapped];
      }
      return wrapped;
    }
    return await this.getTokenAccountsByOwnerForMint(
      connection,
      ownerAddress,
      this.quoteMintAddress
    );
  }

  async findOpenOrdersAccountsForOwner(
    connection: Connection,
    ownerAddress: PublicKey,
    cacheDurationMs = 0
  ): Promise<OpenOrders[]> {
    const strOwner = ownerAddress.toBase58();
    const now = new Date().getTime();
    if (
      strOwner in this._openOrdersAccountsCache &&
      now - this._openOrdersAccountsCache[strOwner].ts < cacheDurationMs
    ) {
      return this._openOrdersAccountsCache[strOwner].accounts;
    }
    const openOrdersAccountsForOwner = await OpenOrders.findForMarketAndOwner(
      connection,
      this.address,
      ownerAddress,
      this._programId
    );
    this._openOrdersAccountsCache[strOwner] = {
      accounts: openOrdersAccountsForOwner,
      ts: now,
    };
    return openOrdersAccountsForOwner;
  }

  async replaceOrders(
    connection: Connection,
    accounts: OrderParamsAccounts,
    orders: OrderParamsBase[],
    cacheDurationMs = 0
  ) {
    if (!accounts.openOrdersAccount && !accounts.openOrdersAddressKey) {
      const ownerAddress: PublicKey =
        accounts.owner.publicKey ?? accounts.owner;
      const openOrdersAccounts = await this.findOpenOrdersAccountsForOwner(
        connection,
        ownerAddress,
        cacheDurationMs
      );
      accounts.openOrdersAddressKey = openOrdersAccounts[0].address;
    }

    const transaction = new Transaction();
    transaction.add(
      this.makeReplaceOrdersByClientIdsInstruction(accounts, orders)
    );
    return await this._sendTransaction(connection, transaction, [
      accounts.owner,
    ]);
  }

  async placeOrder(
    connection: Connection,
    {
      owner,
      payer,
      side,
      price,
      size,
      orderType = 'limit',
      clientId,
      openOrdersAddressKey,
      openOrdersAccount,
      feeDiscountPubkey,
      maxTs,
      replaceIfExists = false,
    }: OrderParams
  ) {
    const { transaction, signers } =
      await this.makePlaceOrderTransaction<Account>(connection, {
        owner,
        payer,
        side,
        price,
        size,
        orderType,
        clientId,
        openOrdersAddressKey,
        openOrdersAccount,
        feeDiscountPubkey,
        maxTs,
        replaceIfExists,
      });
    return await this._sendTransaction(connection, transaction, [
      owner,
      ...signers,
    ]);
  }

  async placeOrders(
    connection: Connection,
    orders: OrderParams<Account>[]
  ): Promise<TransactionSignature[]> {
    const transactionSignatures = new Array<TransactionSignature>();
    const ownersMap = new Map<
      Account,
      { transaction: Transaction; signers: Array<Account> }
    >();

    for (const {
      owner,
      payer,
      side,
      price,
      size,
      orderType = 'limit',
      clientId,
      openOrdersAddressKey,
      openOrdersAccount,
      feeDiscountPubkey,
      maxTs,
      replaceIfExists = false,
    } of orders) {
      let item = ownersMap.get(owner);
      if (!item) {
        item = { transaction: new Transaction(), signers: [] };
        ownersMap.set(owner, item);
      }

      const transaction: Transaction = item.transaction;
      const signers: Array<Account> = item.signers;

      const partial = await this.makePlaceOrderTransactionForBatch(
        transaction,
        connection,
        {
          owner,
          payer,
          side,
          price,
          size,
          orderType,
          clientId,
          openOrdersAddressKey,
          openOrdersAccount,
          feeDiscountPubkey,
          maxTs,
          replaceIfExists,
        } as OrderParams
      );

      signers.push(...partial.signers);
    }

    const sendTransaction = async (
      entry: [Account, { transaction: Transaction; signers: Array<Account> }]
    ) => {
      transactionSignatures.push(
        await this._sendTransaction(connection, entry[1].transaction, [
          entry[0],
          ...entry[1].signers,
        ])
      );
    };

    await promiseAllInBatches(sendTransaction, Array.from(ownersMap.entries()));

    return transactionSignatures;
  }

  getSplTokenBalanceFromAccountInfo(
    accountInfo: AccountInfo<Buffer>,
    decimals: number
  ): number {
    return divideBnToNumber(
      new BN(accountInfo.data.slice(64, 72), 10, 'le'),
      new BN(10).pow(new BN(decimals))
    );
  }

  get supportsSrmFeeDiscounts() {
    return supportsSrmFeeDiscounts(this._programId);
  }

  get supportsReferralFees() {
    return getLayoutVersion(this._programId) > 1;
  }

  get usesRequestQueue() {
    return getLayoutVersion(this._programId) <= 2;
  }

  async findFeeDiscountKeys(
    connection: Connection,
    ownerAddress: PublicKey,
    cacheDurationMs = 0
  ): Promise<
    Array<{
      pubkey: PublicKey;
      feeTier: number;
      balance: number;
      mint: PublicKey;
    }>
  > {
    let sortedAccounts: Array<{
      balance: number;
      mint: PublicKey;
      pubkey: PublicKey;
      feeTier: number;
    }> = [];
    const now = new Date().getTime();
    const strOwner = ownerAddress.toBase58();
    if (
      strOwner in this._feeDiscountKeysCache &&
      now - this._feeDiscountKeysCache[strOwner].ts < cacheDurationMs
    ) {
      return this._feeDiscountKeysCache[strOwner].accounts;
    }

    if (this.supportsSrmFeeDiscounts) {
      // Fee discounts based on (M)SRM holdings supported in newer versions
      const msrmAccounts = (
        await this.getTokenAccountsByOwnerForMint(
          connection,
          ownerAddress,
          MSRM_MINT
        )
      ).map(({ pubkey, account }) => {
        const balance = this.getSplTokenBalanceFromAccountInfo(
          account,
          MSRM_DECIMALS
        );
        return {
          pubkey,
          mint: MSRM_MINT,
          balance,
          feeTier: getFeeTier(balance, 0),
        };
      });
      const srmAccounts = (
        await this.getTokenAccountsByOwnerForMint(
          connection,
          ownerAddress,
          SRM_MINT
        )
      ).map(({ pubkey, account }) => {
        const balance = this.getSplTokenBalanceFromAccountInfo(
          account,
          SRM_DECIMALS
        );
        return {
          pubkey,
          mint: SRM_MINT,
          balance,
          feeTier: getFeeTier(0, balance),
        };
      });
      sortedAccounts = msrmAccounts.concat(srmAccounts).sort((a, b) => {
        if (a.feeTier > b.feeTier) {
          return -1;
        } else if (a.feeTier < b.feeTier) {
          return 1;
        } else {
          if (a.balance > b.balance) {
            return -1;
          } else if (a.balance < b.balance) {
            return 1;
          } else {
            return 0;
          }
        }
      });
    }
    this._feeDiscountKeysCache[strOwner] = {
      accounts: sortedAccounts,
      ts: now,
    };
    return sortedAccounts;
  }

  async findBestFeeDiscountKey(
    connection: Connection,
    ownerAddress: PublicKey,
    cacheDurationMs = 30000
  ): Promise<{ pubkey: PublicKey | null; feeTier: number }> {
    const accounts = await this.findFeeDiscountKeys(
      connection,
      ownerAddress,
      cacheDurationMs
    );
    if (accounts.length > 0) {
      return {
        pubkey: accounts[0].pubkey,
        feeTier: accounts[0].feeTier,
      };
    }
    return {
      pubkey: null,
      feeTier: 0,
    };
  }

  async makePlaceOrderTransaction<T extends PublicKey | Account>(
    connection: Connection,
    {
      owner,
      payer,
      side,
      price,
      size,
      orderType = 'limit',
      clientId,
      openOrdersAddressKey,
      openOrdersAccount,
      feeDiscountPubkey = undefined,
      selfTradeBehavior = 'decrementTake',
      maxTs,
      replaceIfExists = false,
    }: OrderParams<T>,
    cacheDurationMs = 0,
    feeDiscountPubkeyCacheDurationMs = 0
  ) {
    const ownerAddress: PublicKey = (owner as Account).publicKey ?? owner;
    const openOrdersAccounts = await this.findOpenOrdersAccountsForOwner(
      connection,
      ownerAddress,
      cacheDurationMs
    );
    const transaction = new Transaction();
    const signers: Account[] = [];

    // Fetch an SRM fee discount key if the market supports discounts and it is not supplied
    let useFeeDiscountPubkey: PublicKey | null;
    if (feeDiscountPubkey) {
      useFeeDiscountPubkey = feeDiscountPubkey;
    } else if (
      feeDiscountPubkey === undefined &&
      this.supportsSrmFeeDiscounts
    ) {
      useFeeDiscountPubkey = (
        await this.findBestFeeDiscountKey(
          connection,
          ownerAddress,
          feeDiscountPubkeyCacheDurationMs
        )
      ).pubkey;
    } else {
      useFeeDiscountPubkey = null;
    }

    let openOrdersAddress: PublicKey;
    if (openOrdersAccounts.length === 0) {
      let account;
      if (openOrdersAccount) {
        account = openOrdersAccount;
      } else {
        account = new Account();
      }
      transaction.add(
        await OpenOrders.makeCreateAccountTransaction(
          connection,
          this.address,
          ownerAddress,
          account.publicKey,
          this._programId
        )
      );
      openOrdersAddress = account.publicKey;
      signers.push(account);
      // refresh the cache of open order accounts on next fetch
      this._openOrdersAccountsCache[ownerAddress.toBase58()].ts = 0;
    } else if (openOrdersAccount) {
      openOrdersAddress = openOrdersAccount.publicKey;
    } else if (openOrdersAddressKey) {
      openOrdersAddress = openOrdersAddressKey;
    } else {
      openOrdersAddress = openOrdersAccounts[0].address;
    }

    let wrappedSolAccount: Account | null = null;
    if (payer.equals(ownerAddress)) {
      if (
        (side === 'buy' && this.quoteMintAddress.equals(WRAPPED_SOL_MINT)) ||
        (side === 'sell' && this.baseMintAddress.equals(WRAPPED_SOL_MINT))
      ) {
        wrappedSolAccount = new Account();
        let lamports;
        if (side === 'buy') {
          lamports = Math.round(price * size * 1.01 * LAMPORTS_PER_SOL);
          if (openOrdersAccounts.length > 0) {
            lamports -= openOrdersAccounts[0].quoteTokenFree.toNumber();
          }
        } else {
          lamports = Math.round(size * LAMPORTS_PER_SOL);
          if (openOrdersAccounts.length > 0) {
            lamports -= openOrdersAccounts[0].baseTokenFree.toNumber();
          }
        }
        lamports = Math.max(lamports, 0) + 1e7;
        transaction.add(
          SystemProgram.createAccount({
            fromPubkey: ownerAddress,
            newAccountPubkey: wrappedSolAccount.publicKey,
            lamports,
            space: 165,
            programId: TOKEN_PROGRAM_ID,
          })
        );
        transaction.add(
          initializeAccount({
            account: wrappedSolAccount.publicKey,
            mint: WRAPPED_SOL_MINT,
            owner: ownerAddress,
          })
        );
        signers.push(wrappedSolAccount);
      } else {
        throw new Error('Invalid payer account');
      }
    }

    const placeOrderInstruction = this.makePlaceOrderInstruction(connection, {
      owner,
      payer: wrappedSolAccount?.publicKey ?? payer,
      side,
      price,
      size,
      orderType,
      clientId,
      openOrdersAddressKey: openOrdersAddress,
      feeDiscountPubkey: useFeeDiscountPubkey,
      selfTradeBehavior,
      maxTs,
      replaceIfExists,
    });
    transaction.add(placeOrderInstruction);

    if (wrappedSolAccount) {
      transaction.add(
        closeAccount({
          source: wrappedSolAccount.publicKey,
          destination: ownerAddress,
          owner: ownerAddress,
        })
      );
    }

    return { transaction, signers, payer: owner };
  }

  async makePlaceOrderTransactionForBatch<T extends PublicKey | Account>(
    transaction: Transaction,
    connection: Connection,
    {
      owner,
      payer,
      side,
      price,
      size,
      orderType = 'limit',
      clientId,
      openOrdersAddressKey,
      openOrdersAccount,
      feeDiscountPubkey = undefined,
      selfTradeBehavior = 'decrementTake',
      maxTs,
      replaceIfExists = false,
    }: OrderParams<T>,
    cacheDurationMs = 0,
    feeDiscountPubkeyCacheDurationMs = 0
  ) {
    const ownerAddress: PublicKey = (owner as Account).publicKey ?? owner;
    const openOrdersAccounts = await this.findOpenOrdersAccountsForOwner(
      connection,
      ownerAddress,
      cacheDurationMs
    );
    const signers: Account[] = [];

    // Fetch an SRM fee discount key if the market supports discounts and it is not supplied
    let useFeeDiscountPubkey: PublicKey | null;
    if (feeDiscountPubkey) {
      useFeeDiscountPubkey = feeDiscountPubkey;
    } else if (
      feeDiscountPubkey === undefined &&
      this.supportsSrmFeeDiscounts
    ) {
      useFeeDiscountPubkey = (
        await this.findBestFeeDiscountKey(
          connection,
          ownerAddress,
          feeDiscountPubkeyCacheDurationMs
        )
      ).pubkey;
    } else {
      useFeeDiscountPubkey = null;
    }

    let openOrdersAddress: PublicKey;
    if (openOrdersAccounts.length === 0) {
      let account;
      if (openOrdersAccount) {
        account = openOrdersAccount;
      } else {
        account = new Account();
      }
      transaction.add(
        await OpenOrders.makeCreateAccountTransaction(
          connection,
          this.address,
          ownerAddress,
          account.publicKey,
          this._programId
        )
      );
      openOrdersAddress = account.publicKey;
      signers.push(account);
      // refresh the cache of open order accounts on next fetch
      this._openOrdersAccountsCache[ownerAddress.toBase58()].ts = 0;
    } else if (openOrdersAccount) {
      openOrdersAddress = openOrdersAccount.publicKey;
    } else if (openOrdersAddressKey) {
      openOrdersAddress = openOrdersAddressKey;
    } else {
      openOrdersAddress = openOrdersAccounts[0].address;
    }

    let wrappedSolAccount: Account | null = null;
    if (payer.equals(ownerAddress)) {
      if (
        (side === 'buy' && this.quoteMintAddress.equals(WRAPPED_SOL_MINT)) ||
        (side === 'sell' && this.baseMintAddress.equals(WRAPPED_SOL_MINT))
      ) {
        wrappedSolAccount = new Account();
        let lamports;
        if (side === 'buy') {
          lamports = Math.round(price * size * 1.01 * LAMPORTS_PER_SOL);
          if (openOrdersAccounts.length > 0) {
            lamports -= openOrdersAccounts[0].quoteTokenFree.toNumber();
          }
        } else {
          lamports = Math.round(size * LAMPORTS_PER_SOL);
          if (openOrdersAccounts.length > 0) {
            lamports -= openOrdersAccounts[0].baseTokenFree.toNumber();
          }
        }
        lamports = Math.max(lamports, 0) + 1e7;
        transaction.add(
          SystemProgram.createAccount({
            fromPubkey: ownerAddress,
            newAccountPubkey: wrappedSolAccount.publicKey,
            lamports,
            space: 165,
            programId: TOKEN_PROGRAM_ID,
          })
        );
        transaction.add(
          initializeAccount({
            account: wrappedSolAccount.publicKey,
            mint: WRAPPED_SOL_MINT,
            owner: ownerAddress,
          })
        );
        signers.push(wrappedSolAccount);
      } else {
        throw new Error('Invalid payer account');
      }
    }

    const placeOrderInstruction = this.makePlaceOrderInstruction(connection, {
      owner,
      payer: wrappedSolAccount?.publicKey ?? payer,
      side,
      price,
      size,
      orderType,
      clientId,
      openOrdersAddressKey: openOrdersAddress,
      feeDiscountPubkey: useFeeDiscountPubkey,
      selfTradeBehavior,
      maxTs,
      replaceIfExists,
    });
    transaction.add(placeOrderInstruction);

    if (wrappedSolAccount) {
      transaction.add(
        closeAccount({
          source: wrappedSolAccount.publicKey,
          destination: ownerAddress,
          owner: ownerAddress,
        })
      );
    }

    return { transaction, signers, payer: owner };
  }

  makePlaceOrderInstruction<T extends PublicKey | Account>(
    _connection: Connection,
    params: OrderParams<T>
  ): TransactionInstruction {
    const {
      owner,
      payer,
      side,
      price,
      size,
      orderType = 'limit',
      clientId,
      openOrdersAddressKey,
      openOrdersAccount,
      feeDiscountPubkey = null,
    } = params;
    const ownerAddress: PublicKey = (owner as Account).publicKey ?? owner;
    if (this.baseSizeNumberToLots(size).lte(new BN(0))) {
      throw new Error('size too small');
    }
    if (this.priceNumberToLots(price).lte(new BN(0))) {
      throw new Error('invalid price');
    }
    if (this.usesRequestQueue) {
      return DexInstructions.newOrder({
        market: this.address,
        requestQueue: this._decoded.requestQueue,
        baseVault: this._decoded.baseVault,
        quoteVault: this._decoded.quoteVault,
        openOrders: openOrdersAccount
          ? openOrdersAccount.publicKey
          : openOrdersAddressKey,
        owner: ownerAddress,
        payer,
        side,
        limitPrice: this.priceNumberToLots(price),
        maxQuantity: this.baseSizeNumberToLots(size),
        orderType,
        clientId,
        programId: this._programId,
        feeDiscountPubkey: this.supportsSrmFeeDiscounts
          ? feeDiscountPubkey
          : null,
      });
    } else {
      return this.makeNewOrderV3Instruction(params);
    }
  }

  makeNewOrderV3Instruction<T extends PublicKey | Account>(
    params: OrderParams<T>
  ): TransactionInstruction {
    const {
      owner,
      payer,
      side,
      price,
      size,
      orderType = 'limit',
      clientId,
      openOrdersAddressKey,
      openOrdersAccount,
      feeDiscountPubkey = null,
      selfTradeBehavior = 'decrementTake',
      programId,
      maxTs,
      replaceIfExists,
    } = params;
    const ownerAddress: PublicKey = (owner as Account).publicKey ?? owner;
    return DexInstructions.newOrderV3({
      market: this.address,
      bids: this._decoded.bids,
      asks: this._decoded.asks,
      requestQueue: this._decoded.requestQueue,
      eventQueue: this._decoded.eventQueue,
      baseVault: this._decoded.baseVault,
      quoteVault: this._decoded.quoteVault,
      openOrders: openOrdersAccount
        ? openOrdersAccount.publicKey
        : openOrdersAddressKey,
      owner: ownerAddress,
      payer,
      side,
      limitPrice: this.priceNumberToLots(price),
      maxBaseQuantity: this.baseSizeNumberToLots(size),
      maxQuoteQuantity: new BN(this._decoded.quoteLotSize.toNumber()).mul(
        this.baseSizeNumberToLots(size).mul(this.priceNumberToLots(price))
      ),
      orderType,
      clientId,
      programId: programId ?? this._programId,
      selfTradeBehavior,
      feeDiscountPubkey: this.supportsSrmFeeDiscounts
        ? feeDiscountPubkey
        : null,
      maxTs,
      replaceIfExists,
    });
  }

  makeReplaceOrdersByClientIdsInstruction<T extends PublicKey | Account>(
    accounts: OrderParamsAccounts<T>,
    orders: OrderParamsBase<T>[]
  ): TransactionInstruction {
    const ownerAddress: PublicKey =
      (accounts.owner as Account).publicKey ?? accounts.owner;
    return DexInstructions.replaceOrdersByClientIds({
      market: this.address,
      bids: this._decoded.bids,
      asks: this._decoded.asks,
      requestQueue: this._decoded.requestQueue,
      eventQueue: this._decoded.eventQueue,
      baseVault: this._decoded.baseVault,
      quoteVault: this._decoded.quoteVault,
      openOrders: accounts.openOrdersAccount
        ? accounts.openOrdersAccount.publicKey
        : accounts.openOrdersAddressKey,
      owner: ownerAddress,
      payer: accounts.payer,
      programId: accounts.programId ?? this._programId,
      feeDiscountPubkey: this.supportsSrmFeeDiscounts
        ? accounts.feeDiscountPubkey
        : null,
      orders: orders.map((order) => ({
        side: order.side,
        limitPrice: this.priceNumberToLots(order.price),
        maxBaseQuantity: this.baseSizeNumberToLots(order.size),
        maxQuoteQuantity: new BN(this._decoded.quoteLotSize.toNumber()).mul(
          this.baseSizeNumberToLots(order.size).mul(
            this.priceNumberToLots(order.price)
          )
        ),
        orderType: order.orderType,
        clientId: order.clientId,
        programId: accounts.programId ?? this._programId,
        selfTradeBehavior: order.selfTradeBehavior,
        maxTs: order.maxTs,
      })),
    });
  }

  private async _sendTransaction(
    connection: Connection,
    transaction: Transaction,
    signers: Array<Account>
  ): Promise<TransactionSignature> {
    const signature = await connection.sendTransaction(transaction, signers, {
      skipPreflight: this._skipPreflight,
    });
    const { value } = await connection.confirmTransaction(
      signature,
      this._commitment
    );
    if (value?.err) {
      throw new Error(JSON.stringify(value.err));
    }
    return signature;
  }

  async cancelOrderByClientId(
    connection: Connection,
    owner: Account,
    openOrders: PublicKey,
    clientId: BN
  ) {
    const transaction = await this.makeCancelOrderByClientIdTransaction(
      connection,
      owner.publicKey,
      openOrders,
      clientId
    );
    return await this._sendTransaction(connection, transaction, [owner]);
  }

  async cancelOrdersByClientIds(
    connection: Connection,
    owner: Account,
    openOrders: PublicKey,
    clientIds: BN[]
  ) {
    const transaction = await this.makeCancelOrdersByClientIdsTransaction(
      connection,
      owner.publicKey,
      openOrders,
      clientIds
    );
    return await this._sendTransaction(connection, transaction, [owner]);
  }

  async makeCancelOrderByClientIdTransaction(
    _connection: Connection,
    owner: PublicKey,
    openOrders: PublicKey,
    clientId: BN
  ) {
    const transaction = new Transaction();
    if (this.usesRequestQueue) {
      transaction.add(
        DexInstructions.cancelOrderByClientId({
          market: this.address,
          owner,
          openOrders,
          requestQueue: this._decoded.requestQueue,
          clientId,
          programId: this._programId,
        })
      );
    } else {
      transaction.add(
        DexInstructions.cancelOrderByClientIdV2({
          market: this.address,
          openOrders,
          owner,
          bids: this._decoded.bids,
          asks: this._decoded.asks,
          eventQueue: this._decoded.eventQueue,
          clientId,
          programId: this._programId,
        })
      );
    }
    return transaction;
  }

  async makeCancelOrdersByClientIdsTransaction(
    _connection: Connection,
    owner: PublicKey,
    openOrders: PublicKey,
    clientIds: BN[]
  ) {
    const transaction = new Transaction();
    transaction.add(
      DexInstructions.cancelOrdersByClientIds({
        market: this.address,
        openOrders,
        owner,
        bids: this._decoded.bids,
        asks: this._decoded.asks,
        eventQueue: this._decoded.eventQueue,
        clientIds,
        programId: this._programId,
      })
    );
    return transaction;
  }

  async cancelOrder(connection: Connection, owner: Account, order: Order) {
    const transaction = await this.makeCancelOrderTransaction(
      connection,
      owner.publicKey,
      order
    );
    return await this._sendTransaction(connection, transaction, [owner]);
  }

  async cancelOrders(
    connection: Connection,
    owner: Account,
    orders: Order[]
  ): Promise<TransactionSignature> {
    if (!orders.length) throw new Error('No orders provided');

    const transaction = new Transaction();

    for (const order of orders) {
      await this.makeCancelOrderTransactionForBatch(
        transaction,
        connection,
        owner.publicKey,
        order
      );
    }

    return await this._sendTransaction(connection, transaction, [owner]);
  }

  async makeCancelOrderTransaction(
    connection: Connection,
    owner: PublicKey,
    order: Order
  ) {
    const transaction = new Transaction();
    transaction.add(this.makeCancelOrderInstruction(connection, owner, order));
    return transaction;
  }

  async makeCancelOrderTransactionForBatch(
    transaction: Transaction,
    connection: Connection,
    owner: PublicKey,
    order: Order
  ) {
    transaction.add(this.makeCancelOrderInstruction(connection, owner, order));

    return transaction;
  }

  makeCancelOrderInstruction(
    _connection: Connection,
    owner: PublicKey,
    order: Order
  ) {
    if (this.usesRequestQueue) {
      return DexInstructions.cancelOrder({
        market: this.address,
        owner,
        openOrders: order.openOrdersAddress,
        requestQueue: this._decoded.requestQueue,
        side: order.side,
        orderId: order.orderId,
        openOrdersSlot: order.openOrdersSlot,
        programId: this._programId,
      });
    } else {
      return DexInstructions.cancelOrderV2({
        market: this.address,
        owner,
        openOrders: order.openOrdersAddress,
        bids: this._decoded.bids,
        asks: this._decoded.asks,
        eventQueue: this._decoded.eventQueue,
        side: order.side,
        orderId: order.orderId,
        openOrdersSlot: order.openOrdersSlot,
        programId: this._programId,
      });
    }
  }

  public makeConsumeEventsInstruction(
    openOrdersAccounts: Array<PublicKey>,
    limit: number
  ): TransactionInstruction {
    return DexInstructions.consumeEvents({
      market: this.address,
      eventQueue: this._decoded.eventQueue,
      coinFee: this._decoded.eventQueue,
      pcFee: this._decoded.eventQueue,
      openOrdersAccounts,
      limit,
      programId: this._programId,
    });
  }

  public makeConsumeEventsPermissionedInstruction(
    openOrdersAccounts: Array<PublicKey>,
    limit: number
  ): TransactionInstruction {
    return DexInstructions.consumeEventsPermissioned({
      market: this.address,
      eventQueue: this._decoded.eventQueue,
      crankAuthority: this._decoded.consumeEventsAuthority,
      openOrdersAccounts,
      limit,
      programId: this._programId,
    });
  }

  async settleFunds(
    connection: Connection,
    owner: Account,
    openOrders: OpenOrders,
    baseWallet: PublicKey,
    quoteWallet: PublicKey,
    referrerQuoteWallet: PublicKey | null = null
  ) {
    if (!openOrders.owner.equals(owner.publicKey)) {
      throw new Error('Invalid open orders account');
    }
    if (referrerQuoteWallet && !this.supportsReferralFees) {
      throw new Error('This program ID does not support referrerQuoteWallet');
    }
    const { transaction, signers } = await this.makeSettleFundsTransaction(
      connection,
      openOrders,
      baseWallet,
      quoteWallet,
      referrerQuoteWallet
    );
    return await this._sendTransaction(connection, transaction, [
      owner,
      ...signers,
    ]);
  }

  async settleSeveralFunds(
    connection: Connection,
    settlements: {
      owner: Account;
      openOrders: OpenOrders;
      baseWallet: PublicKey;
      quoteWallet: PublicKey;
      referrerQuoteWallet: PublicKey | null;
    }[],
    transaction: Transaction = new Transaction()
  ): Promise<TransactionSignature[]> {
    const transactionSignatures = new Array<TransactionSignature>();
    const ownersMap = new Map<
      Account,
      { transaction: Transaction; signers: Array<Account> }
    >();
    const onwersCount = new Set(settlements.map((item) => item.owner)).size;

    for (const {
      owner,
      openOrders,
      baseWallet,
      quoteWallet,
      referrerQuoteWallet = null,
    } of settlements) {
      if (!openOrders.owner.equals(owner.publicKey)) {
        throw new Error('Invalid open orders account');
      }

      if (referrerQuoteWallet && !this.supportsReferralFees) {
        throw new Error('This program ID does not support referrerQuoteWallet');
      }

      let item = ownersMap.get(owner);
      if (!item) {
        item = { transaction: new Transaction(), signers: [] };
        ownersMap.set(owner, item);
      }

      const targetTransaction: Transaction =
        onwersCount == 1 ? transaction : item.transaction;
      const signers: Array<Account> = item.signers;

      const partial = await this.makeSettleFundsTransactionForBatch(
        targetTransaction,
        connection,
        openOrders,
        baseWallet,
        quoteWallet,
        referrerQuoteWallet
      );

      signers.push(...partial.signers);
    }

    const sendTransaction = async (
      entry: [Account, { transaction: Transaction; signers: Array<Account> }]
    ) => {
      transactionSignatures.push(
        await this._sendTransaction(connection, entry[1].transaction, [
          entry[0],
          ...entry[1].signers,
        ])
      );
    };

    await promiseAllInBatches(sendTransaction, Array.from(ownersMap.entries()));

    return transactionSignatures;
  }

  async makeSettleFundsTransaction(
    connection: Connection,
    openOrders: OpenOrders,
    baseWallet: PublicKey,
    quoteWallet: PublicKey,
    referrerQuoteWallet: PublicKey | null = null
  ) {
    const vaultSigner = await PublicKey.createProgramAddress(
      [
        this.address.toBuffer(),
        this._decoded.vaultSignerNonce.toArrayLike(Buffer, 'le', 8),
      ],
      this._programId
    );

    const transaction = new Transaction();
    const signers: Account[] = [];

    let wrappedSolAccount: Account | null = null;
    if (
      (this.baseMintAddress.equals(WRAPPED_SOL_MINT) &&
        baseWallet.equals(openOrders.owner)) ||
      (this.quoteMintAddress.equals(WRAPPED_SOL_MINT) &&
        quoteWallet.equals(openOrders.owner))
    ) {
      wrappedSolAccount = new Account();
      transaction.add(
        SystemProgram.createAccount({
          fromPubkey: openOrders.owner,
          newAccountPubkey: wrappedSolAccount.publicKey,
          lamports: await connection.getMinimumBalanceForRentExemption(165),
          space: 165,
          programId: TOKEN_PROGRAM_ID,
        })
      );
      transaction.add(
        initializeAccount({
          account: wrappedSolAccount.publicKey,
          mint: WRAPPED_SOL_MINT,
          owner: openOrders.owner,
        })
      );
      signers.push(wrappedSolAccount);
    }

    transaction.add(
      DexInstructions.settleFunds({
        market: this.address,
        openOrders: openOrders.address,
        owner: openOrders.owner,
        baseVault: this._decoded.baseVault,
        quoteVault: this._decoded.quoteVault,
        baseWallet:
          baseWallet.equals(openOrders.owner) && wrappedSolAccount
            ? wrappedSolAccount.publicKey
            : baseWallet,
        quoteWallet:
          quoteWallet.equals(openOrders.owner) && wrappedSolAccount
            ? wrappedSolAccount.publicKey
            : quoteWallet,
        vaultSigner,
        programId: this._programId,
        referrerQuoteWallet,
      })
    );

    if (wrappedSolAccount) {
      transaction.add(
        closeAccount({
          source: wrappedSolAccount.publicKey,
          destination: openOrders.owner,
          owner: openOrders.owner,
        })
      );
    }

    return { transaction, signers, payer: openOrders.owner };
  }

  async makeSettleFundsTransactionForBatch(
    transaction: Transaction,
    connection: Connection,
    openOrders: OpenOrders,
    baseWallet: PublicKey,
    quoteWallet: PublicKey,
    referrerQuoteWallet: PublicKey | null = null
  ) {
    const vaultSigner = await PublicKey.createProgramAddress(
      [
        this.address.toBuffer(),
        this._decoded.vaultSignerNonce.toArrayLike(Buffer, 'le', 8),
      ],
      this._programId
    );

    const signers: Account[] = [];

    let wrappedSolAccount: Account | null = null;
    if (
      (this.baseMintAddress.equals(WRAPPED_SOL_MINT) &&
        baseWallet.equals(openOrders.owner)) ||
      (this.quoteMintAddress.equals(WRAPPED_SOL_MINT) &&
        quoteWallet.equals(openOrders.owner))
    ) {
      wrappedSolAccount = new Account();
      transaction.add(
        SystemProgram.createAccount({
          fromPubkey: openOrders.owner,
          newAccountPubkey: wrappedSolAccount.publicKey,
          lamports: await connection.getMinimumBalanceForRentExemption(165),
          space: 165,
          programId: TOKEN_PROGRAM_ID,
        })
      );
      transaction.add(
        initializeAccount({
          account: wrappedSolAccount.publicKey,
          mint: WRAPPED_SOL_MINT,
          owner: openOrders.owner,
        })
      );
      signers.push(wrappedSolAccount);
    }

    transaction.add(
      DexInstructions.settleFunds({
        market: this.address,
        openOrders: openOrders.address,
        owner: openOrders.owner,
        baseVault: this._decoded.baseVault,
        quoteVault: this._decoded.quoteVault,
        baseWallet:
          baseWallet.equals(openOrders.owner) && wrappedSolAccount
            ? wrappedSolAccount.publicKey
            : baseWallet,
        quoteWallet:
          quoteWallet.equals(openOrders.owner) && wrappedSolAccount
            ? wrappedSolAccount.publicKey
            : quoteWallet,
        vaultSigner,
        programId: this._programId,
        referrerQuoteWallet,
      })
    );

    if (wrappedSolAccount) {
      transaction.add(
        closeAccount({
          source: wrappedSolAccount.publicKey,
          destination: openOrders.owner,
          owner: openOrders.owner,
        })
      );
    }

    return { transaction, signers, payer: openOrders.owner };
  }

  async matchOrders(connection: Connection, feePayer: Account, limit: number) {
    const tx = this.makeMatchOrdersTransaction(limit);
    return await this._sendTransaction(connection, tx, [feePayer]);
  }

  makeMatchOrdersTransaction(limit: number): Transaction {
    const tx = new Transaction();
    tx.add(
      DexInstructions.matchOrders({
        market: this.address,
        requestQueue: this._decoded.requestQueue,
        eventQueue: this._decoded.eventQueue,
        bids: this._decoded.bids,
        asks: this._decoded.asks,
        baseVault: this._decoded.baseVault,
        quoteVault: this._decoded.quoteVault,
        limit,
        programId: this._programId,
      })
    );
    return tx;
  }

  async loadRequestQueue(connection: Connection) {
    const { data } = throwIfNull(
      await connection.getAccountInfo(this._decoded.requestQueue)
    );
    return decodeRequestQueue(data);
  }

  async loadEventQueue(connection: Connection) {
    const { data } = throwIfNull(
      await connection.getAccountInfo(this._decoded.eventQueue)
    );
    return decodeEventQueue(data);
  }

  async loadFills(connection: Connection, limit = 100) {
    // TODO: once there's a separate source of fills use that instead
    const { data } = throwIfNull(
      await connection.getAccountInfo(this._decoded.eventQueue)
    );
    const events = decodeEventQueue(data, limit);
    return events
      .filter(
        (event) => event.eventFlags.fill && event.nativeQuantityPaid.gtn(0)
      )
      .map(this.parseFillEvent.bind(this));
  }

  parseFillEvent(event: any) {
    let size, price, side, priceBeforeFees;
    if (event.eventFlags.bid) {
      side = 'buy';
      priceBeforeFees = event.eventFlags.maker
        ? event.nativeQuantityPaid.add(event.nativeFeeOrRebate)
        : event.nativeQuantityPaid.sub(event.nativeFeeOrRebate);
      price = divideBnToNumber(
        priceBeforeFees.mul(this._baseSplTokenMultiplier),
        this._quoteSplTokenMultiplier.mul(event.nativeQuantityReleased)
      );
      size = divideBnToNumber(
        event.nativeQuantityReleased,
        this._baseSplTokenMultiplier
      );
    } else {
      side = 'sell';
      priceBeforeFees = event.eventFlags.maker
        ? event.nativeQuantityReleased.sub(event.nativeFeeOrRebate)
        : event.nativeQuantityReleased.add(event.nativeFeeOrRebate);
      price = divideBnToNumber(
        priceBeforeFees.mul(this._baseSplTokenMultiplier),
        this._quoteSplTokenMultiplier.mul(event.nativeQuantityPaid)
      );
      size = divideBnToNumber(
        event.nativeQuantityPaid,
        this._baseSplTokenMultiplier
      );
    }
    return {
      ...event,
      side,
      price,
      feeCost:
        this.quoteSplSizeToNumber(event.nativeFeeOrRebate) *
        (event.eventFlags.maker ? -1 : 1),
      size,
    };
  }

  private get _baseSplTokenMultiplier() {
    return new BN(10).pow(new BN(this._baseSplTokenDecimals));
  }

  private get _quoteSplTokenMultiplier() {
    return new BN(10).pow(new BN(this._quoteSplTokenDecimals));
  }

  priceLotsToNumber(price: BN) {
    return divideBnToNumber(
      price.mul(this._decoded.quoteLotSize).mul(this._baseSplTokenMultiplier),
      this._decoded.baseLotSize.mul(this._quoteSplTokenMultiplier)
    );
  }

  priceNumberToLots(price: number): BN {
    return new BN(
      Math.round(
        (price *
          Math.pow(10, this._quoteSplTokenDecimals) *
          this._decoded.baseLotSize.toNumber()) /
          (Math.pow(10, this._baseSplTokenDecimals) *
            this._decoded.quoteLotSize.toNumber())
      )
    );
  }

  baseSplSizeToNumber(size: BN) {
    return divideBnToNumber(size, this._baseSplTokenMultiplier);
  }

  quoteSplSizeToNumber(size: BN) {
    return divideBnToNumber(size, this._quoteSplTokenMultiplier);
  }

  baseSizeLotsToNumber(size: BN) {
    return divideBnToNumber(
      size.mul(this._decoded.baseLotSize),
      this._baseSplTokenMultiplier
    );
  }

  baseSizeNumberToLots(size: number): BN {
    const native = new BN(
      Math.round(size * Math.pow(10, this._baseSplTokenDecimals))
    );
    // rounds down to the nearest lot size
    return native.div(this._decoded.baseLotSize);
  }

  quoteSizeLotsToNumber(size: BN) {
    return divideBnToNumber(
      size.mul(this._decoded.quoteLotSize),
      this._quoteSplTokenMultiplier
    );
  }

  quoteSizeNumberToLots(size: number): BN {
    const native = new BN(
      Math.round(size * Math.pow(10, this._quoteSplTokenDecimals))
    );
    // rounds down to the nearest lot size
    return native.div(this._decoded.quoteLotSize);
  }

  get minOrderSize() {
    return this.baseSizeLotsToNumber(new BN(1));
  }

  get tickSize() {
    return this.priceLotsToNumber(new BN(1));
  }
}

function divideBnToNumber(numerator: BN, denominator: BN): number {
  const quotient = numerator.div(denominator).toNumber();
  const rem = numerator.umod(denominator);
  const gcd = rem.gcd(denominator);
  return quotient + rem.div(gcd).toNumber() / denominator.div(gcd).toNumber();
}

function throwIfNull<T>(value: T | null, message = 'account not found'): T {
  if (value === null) {
    throw new Error(message);
  }
  return value;
}
