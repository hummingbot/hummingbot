// @ts-nocheck

import 'jest-extended';
import {Serum} from '../../../../src/connectors/serum/serum';
import {unpatch} from '../../../services/patch';
import {Solana} from '../../../../src/chains/solana/solana';
import {default as config} from './fixtures/serumConfig';
import {createOrders, getMarkets, getOrderBooks, getTickers} from "../../../../src/clob/clob.controllers";
import {getNewOrderTemplate} from "./fixtures/dummy";
import {addWallet} from "../../../../src/services/wallet/wallet.controllers";
import {getOrCreateTokenAccount} from "../../../../src/chains/solana/solana.controllers";

jest.setTimeout(1000000);

let solana: Solana;
let serum: Serum;

beforeAll(async () => {
  solana = await Solana.getInstance(config.solana.network);

  serum = await Serum.getInstance(config.serum.chain, config.serum.network);
});

afterEach(() => {
  unpatch();
});

it('Temporary', async () => {
  const baseCurrency = 'SOL';
  const quoteCurrency = 'USDT';
  const marketName = `${baseCurrency}/${quoteCurrency}`;

  const commonParameters = {
    chain: config.serum.chain,
    network: config.serum.network,
    connector: config.serum.connector,
  }

  let wallet: any;

  wallet = addWallet({
    chain: config.serum.chain,
    network: config.serum.network,
    privateKey: '',
  });
  console.log('wallet/add', JSON.stringify(wallet, null, 2));

  let tokenAccount = await getOrCreateTokenAccount(
    solana,
    {
      address: config.solana.wallet.owner.address,
      token: baseCurrency,
    }
  );
  console.log('token', JSON.stringify(tokenAccount, null, 2));

  wallet = addWallet({
    chain: config.serum.chain,
    network: config.serum.network,
    privateKey: '',
  });
  console.log('wallet/add', JSON.stringify(wallet, null, 2));

  tokenAccount = await getOrCreateTokenAccount(
    solana,
    {
      address: config.solana.wallet.payer.address,
      token: baseCurrency,
    }
  );
  console.log('token', JSON.stringify(tokenAccount, null, 2));

  // const market = (await getMarkets({
  //   ...commonParameters,
  //   name: marketName,
  // })).body;
  // console.log('market', JSON.stringify(market, null, 2));

  // const orderBook = (await getOrderBooks({
  //   ...commonParameters,
  //   marketName,
  // })).body;
  // console.log('orderBook', JSON.stringify(orderBook, null, 2));

  // const ticker = (await getTickers({
  //   ...commonParameters,
  //   marketName,
  // })).body;
  // console.log('ticker', JSON.stringify(ticker, null, 2));

  const order = await createOrders({
    ...commonParameters,
    order: getNewOrderTemplate()
  });
  console.log('order', JSON.stringify(order, null, 2));

  // const orders = await createNewOrders(3);
  // expect(orders).toBeDefined();
});
