import {Market as SerumMarket} from "@project-serum/serum";
import {OrderParams} from "@project-serum/serum/lib/market";
import token_instructions_1 from "@project-serum/serum/lib/token-instructions";
import web3_js_1, {Account, Connection, PublicKey, Transaction} from "@solana/web3.js";
import {SerumOrderParams} from "./serum.types";

export class Market extends SerumMarket {
  async sendTransaction(connection: Connection, transaction: Transaction, signers) {
    const signature = await connection.sendTransaction(transaction, signers, {
      skipPreflight: this._skipPreflight,
    });
    const { value } = await connection.confirmTransaction(signature, this._commitment);
    if (value === null || value === void 0 ? void 0 : value.err) {
      throw new Error(JSON.stringify(value.err));
    }
    return signature;
  }

  async placeOrders(connection: Connection, orders: SerumOrderParams<Account>[]): Promise<string> {
    const finalTransaction = new Transaction();
    const finalSigners = [];

    for (const { owner, payer, side, price, size, orderType = 'limit', clientId, openOrdersAddressKey, openOrdersAccount, feeDiscountPubkey, maxTs, replaceIfExists = false, } of orders) {
      const { transaction, signers } = await this.makePlaceOrderTransactionForBatch(finalTransaction, connection, {
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

      // TODO remove!!!
      console.log(transaction)

      finalSigners.push(...signers)
    }

    return await this.sendTransaction(connection, finalTransaction, [
      owner,
      ...finalSigners,
    ]);
  }

  async makePlaceOrderTransactionForBatch<T extends PublicKey | Account>(transaction: Transaction, connection: Connection, { owner, payer, side, price, size, orderType, clientId, openOrdersAddressKey, openOrdersAccount, feeDiscountPubkey, selfTradeBehavior, maxTs, replaceIfExists, }: OrderParams<T>, cacheDurationMs?: number, feeDiscountPubkeyCacheDurationMs?: number): Promise<{
      transaction: Transaction;
      signers: Account[];
      payer: T;
  }> {
    var _a, _b;
    // @ts-ignore
    const ownerAddress = (_a = owner.publicKey) !== null && _a !== void 0 ? _a : owner;
    const openOrdersAccounts = await this.findOpenOrdersAccountsForOwner(connection, ownerAddress, cacheDurationMs);
    const signers = [];
    // Fetch an SRM fee discount key if the market supports discounts and it is not supplied
    let useFeeDiscountPubkey;
    if (feeDiscountPubkey) {
      useFeeDiscountPubkey = feeDiscountPubkey;
    }
    else if (feeDiscountPubkey === undefined &&
      this.supportsSrmFeeDiscounts) {
      useFeeDiscountPubkey = (await this.findBestFeeDiscountKey(connection, ownerAddress, feeDiscountPubkeyCacheDurationMs)).pubkey;
    }
    else {
      useFeeDiscountPubkey = null;
    }
    let openOrdersAddress;
    if (openOrdersAccounts.length === 0) {
      let account;
      if (openOrdersAccount) {
        account = openOrdersAccount;
      }
      else {
        account = new web3_js_1.Account();
      }
      transaction.add(await OpenOrders.makeCreateAccountTransaction(connection, this.address, ownerAddress, account.publicKey, this._programId));
      openOrdersAddress = account.publicKey;
      signers.push(account);
      // refresh the cache of open order accounts on next fetch
      this._openOrdersAccountsCache[ownerAddress.toBase58()].ts = 0;
    }
    else if (openOrdersAccount) {
      openOrdersAddress = openOrdersAccount.publicKey;
    }
    else if (openOrdersAddressKey) {
      openOrdersAddress = openOrdersAddressKey;
    }
    else {
      openOrdersAddress = openOrdersAccounts[0].address;
    }
    let wrappedSolAccount = null;
    if (payer.equals(ownerAddress)) {
      if ((side === 'buy' && this.quoteMintAddress.equals(token_instructions_1.WRAPPED_SOL_MINT)) ||
        (side === 'sell' && this.baseMintAddress.equals(token_instructions_1.WRAPPED_SOL_MINT))) {
        wrappedSolAccount = new web3_js_1.Account();
        let lamports;
        if (side === 'buy') {
          lamports = Math.round(price * size * 1.01 * web3_js_1.LAMPORTS_PER_SOL);
          if (openOrdersAccounts.length > 0) {
            lamports -= openOrdersAccounts[0].quoteTokenFree.toNumber();
          }
        }
        else {
          lamports = Math.round(size * web3_js_1.LAMPORTS_PER_SOL);
          if (openOrdersAccounts.length > 0) {
            lamports -= openOrdersAccounts[0].baseTokenFree.toNumber();
          }
        }
        lamports = Math.max(lamports, 0) + 1e7;
        transaction.add(web3_js_1.SystemProgram.createAccount({
          fromPubkey: ownerAddress,
          newAccountPubkey: wrappedSolAccount.publicKey,
          lamports,
          space: 165,
          programId: token_instructions_1.TOKEN_PROGRAM_ID,
        }));
        transaction.add(token_instructions_1.initializeAccount({
          account: wrappedSolAccount.publicKey,
          mint: token_instructions_1.WRAPPED_SOL_MINT,
          owner: ownerAddress,
        }));
        signers.push(wrappedSolAccount);
      }
      else {
        throw new Error('Invalid payer account');
      }
    }
    const placeOrderInstruction = this.makePlaceOrderInstruction(connection, {
      owner,
      payer: (_b = wrappedSolAccount === null || wrappedSolAccount === void 0 ? void 0 : wrappedSolAccount.publicKey) !== null && _b !== void 0 ? _b : payer,
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
      transaction.add(token_instructions_1.closeAccount({
        source: wrappedSolAccount.publicKey,
        destination: ownerAddress,
        owner: ownerAddress,
      }));
    }
    return { transaction, signers, payer: owner };
  }
}