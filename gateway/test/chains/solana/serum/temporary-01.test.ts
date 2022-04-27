// // @ts-ignore // @ts-expect-error
//
// import 'jest-extended';
// import {Serum} from '../../../../src/connectors/serum/serum';
// import {unpatch} from '../../../services/patch';
// import {Solana} from '../../../../src/chains/solana/solana';
// import {default as config} from './fixtures/serumConfig';
// import {
//   cancelOpenOrders,
//   cancelOrders,
//   createOrders, getFilledOrders,
//   getMarkets,
//   getOpenOrders,
//   getOrderBooks,
//   getTickers
// } from "../../../../src/clob/clob.controllers";
// import {getNewOrderTemplate} from "./fixtures/dummy";
// import {addWallet} from "../../../../src/services/wallet/wallet.controllers";
// import {getOrCreateTokenAccount} from "../../../../src/chains/solana/solana.controllers";
// import {Account, Connection, Keypair, PublicKey} from '@solana/web3.js';
// import { Market } from '@project-serum/serum';
//
// jest.setTimeout(1000000);
//
// let solana: Solana;
// let serum: Serum;
//
// beforeAll(async () => {
//   solana = await Solana.getInstance(config.solana.network);
//
//   serum = await Serum.getInstance(config.serum.chain, config.serum.network);
// });
//
// afterEach(() => {
//   unpatch();
// });
//
// it('Temporary 01', async () => {
//   const baseCurrency = 'SOL';
//   const quoteCurrency = 'USDT';
//   const marketName = `${baseCurrency}/${quoteCurrency}`;
//
//   const commonParameters = {
//     chain: config.serum.chain,
//     network: config.serum.network,
//     connector: config.serum.connector,
//   }
//
//   let wallet: any;
//
//   // wallet = addWallet({
//   //   chain: config.serum.chain,
//   //   network: config.serum.network,
//   //   privateKey: '',
//   // });
//   // console.log('wallet/add', JSON.stringify(wallet, null, 2));
//   //
//   // let tokenAccount = await getOrCreateTokenAccount(
//   //   solana,
//   //   {
//   //     address: config.solana.wallet.owner.address,
//   //     token: baseCurrency,
//   //   }
//   // );
//   // console.log('token', JSON.stringify(tokenAccount, null, 2));
//   //
//   // wallet = addWallet({
//   //   chain: config.serum.chain,
//   //   network: config.serum.network,
//   //   privateKey: '',
//   // });
//   // console.log('wallet/add', JSON.stringify(wallet, null, 2));
//   //
//   // tokenAccount = await getOrCreateTokenAccount(
//   //   solana,
//   //   {
//   //     address: config.solana.wallet.payer.address,
//   //     token: baseCurrency,
//   //   }
//   // );
//   // console.log('token', JSON.stringify(tokenAccount, null, 2));
//
//   // const market = (await getMarkets({
//   //   ...commonParameters,
//   //   name: marketName,
//   // })).body;
//   // console.log('market', JSON.stringify(market, null, 2));
//
//   // const orderBook = (await getOrderBooks({
//   //   ...commonParameters,
//   //   marketName,
//   // })).body;
//   // console.log('orderBook', JSON.stringify(orderBook, null, 2));
//   //
//   // const ticker = (await getTickers({
//   //   ...commonParameters,
//   //   marketName,
//   // })).body;
//   // console.log('ticker', JSON.stringify(ticker, null, 2));
//
//   // const order = await createOrders({
//   //   ...commonParameters,
//   //   order: getNewOrderTemplate()
//   // });
//   // console.log('order', JSON.stringify(order, null, 2));
//
//   // const openOrders = await getOpenOrders({
//   //   ...commonParameters,
//   //   ownerAddress: config.solana.wallet.owner.address,
//   // });
//   // console.log('openOrders', JSON.stringify(openOrders, null, 2));
//
//   // const canceledOrders = await cancelOpenOrders({
//   //   ...commonParameters,
//   //   ownerAddress: config.solana.wallet.owner.address,
//   // });
//   // console.log('canceledOrders', JSON.stringify(canceledOrders, null, 2));
//
//   // const filledOrders = await getFilledOrders({
//   //   ...commonParameters,
//   // });
//   // console.log('filledOrders', JSON.stringify(filledOrders, null, 2));
//
//   // const orders = await createNewOrders(3);
//   // expect(orders).toBeDefined();
// });
//
import {Account, Connection, PublicKey} from "@solana/web3.js";
import {Market} from "@project-serum/serum";
import {unpatch} from "../../../services/patch";
import {Solana} from "../../../../src/chains/solana/solana";
import {Serum} from "../../../../src/connectors/serum/serum";
import {default as config} from './fixtures/serumConfig';
import BN from "bn.js";

jest.setTimeout(1000000);

// @ts-ignore
let solana: Solana;
// @ts-ignore
let serum: Serum;

beforeAll(async () => {
  solana = await Solana.getInstance(config.solana.network);

  serum = await Serum.getInstance(config.serum.chain, config.serum.network);
});

afterEach(() => {
  unpatch();
});

it('Temporary 02', async() => {
  let connection = new Connection('https://solana-api.projectserum.com');
  // let connection = new Connection('https://api.testnet.solana.com');
  // let connection = new Connection('https://api.devnet.solana.com');

  // SOL/USDT
  let marketAddress = new PublicKey('HWHvQhFmJB3NUcu1aihKmrKegfVxBEHzwVX6yZCKEsi1');
  let programAddress = new PublicKey('9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin');
  let market = await Market.load(connection, marketAddress, {}, programAddress);

  const ownerKeyPair = await solana.getKeypair(process.env.PUB_KEY_2!);
  let owner = new Account(ownerKeyPair.secretKey);
  // @ts-ignore
  let payer = new PublicKey(process.env.PUB_KEY_2); // spl-token account
  // await market.placeOrder(connection, {
  //   owner,
  //   payer,
  //   side: 'sell', // 'buy' or 'sell'
  //   price: 9999.99,
  //   size: 0.1,
  //   orderType: 'limit', // 'limit', 'ioc', 'postOnly'
  // });

  // Retrieving open orders by owner
  let orders = await market.loadOrdersForOwner(connection, owner.publicKey);
  console.log('orders:')
  console.log(JSON.stringify(orders, null, 2));

  // Cancelling orders
  console.log('canceling orders:')
  for (let order of orders) {
    console.log(JSON.stringify(order, null, 2));
    console.log(JSON.stringify(await market.cancelOrder(connection, owner, order), null, 2));
  }

  // // Retrieving fills
  // console.log('fills:')
  // for (let fill of await market.loadFills(connection)) {
  //   console.log(JSON.stringify(fill, null, 2));
  // }

  console.log('settle funds:')
  for (let openOrders of await market.findOpenOrdersAccountsForOwner(
   connection,
   owner.publicKey,
  )) {
   if (openOrders.baseTokenFree.gt(new BN(0)) || openOrders.quoteTokenFree.gt(new BN(0))) {
     // spl-token accounts to which to send the proceeds from trades
     const base = await market.findBaseTokenAccountsForOwner(connection, owner.publicKey, false);
     const baseTokenAccount = base[0].pubkey;
     const quote = await market.findQuoteTokenAccountsForOwner(connection, owner.publicKey, false);
     const quoteTokenAccount = quote[0].pubkey;

     console.log(JSON.stringify(await market.settleFunds(
       connection,
       owner,
       openOrders,
       baseTokenAccount,
       quoteTokenAccount,
     ), null, 2));
   }
  }

  // // Settle funds
  // for (let openOrders of await market.findOpenOrdersAccountsForOwner(
  //   connection,
  //   owner.publicKey,
  // )) {
  //   if (openOrders.baseTokenFree > 0 || openOrders.quoteTokenFree > 0) {
  //     // spl-token accounts to which to send the proceeds from trades
  //     let baseTokenAccount = new PublicKey('...');
  //     let quoteTokenAccount = new PublicKey('...');
  //
  //     await market.settleFunds(
  //       connection,
  //       owner,
  //       openOrders,
  //       baseTokenAccount,
  //       quoteTokenAccount,
  //     );
  //   }
  // }
});
