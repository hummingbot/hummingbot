import 'jest-extended';
import {Serum} from '../../../../src/connectors/serum/serum';
import {unpatch} from '../../../services/patch';
import {Solana} from '../../../../src/chains/solana/solana';
import {default as config} from './fixtures/serumConfig';
import {createOrders} from '../../../../src/clob/clob.controllers';
import {getNewOrderTemplate} from "./fixtures/dummy";

jest.setTimeout(1000000);

beforeAll(async () => {
  await Solana.getInstance(config.solana.network);

  await Serum.getInstance(config.serum.chain, config.serum.network);
});

afterEach(() => {
  unpatch();
});

it('Temporary 01', async () => {
  const marketNames = ['SOL/USDT', 'SOL/USDC'];
  // @ts-ignore
  const marketName = marketNames[0];

  const orderIds = ['1', '2', '3'];
  // @ts-ignore
  const orderId = orderIds[0];

  // @ts-ignore
  const commonParameters = {
    chain: config.serum.chain,
    network: config.serum.network,
    connector: config.serum.connector,
  }

  // @ts-ignore
  let result: any;

  // result = (await getMarkets({
  //   ...commonParameters,
  //   name: marketName,
  // })).body;
  // console.log('markets:', JSON.stringify(result, null, 2));
  //
  // result = (await getMarkets({
  //   ...commonParameters,
  //   names: marketNames,
  // })).body;
  // console.log('markets:', JSON.stringify(result, null, 2));
  //
  // result = (await getMarkets({
  //   ...commonParameters
  // })).body;
  // console.log('markets:', JSON.stringify(result, null, 2));

  // result = (await getOrderBooks({
  //   ...commonParameters,
  //   marketName: marketName,
  // })).body;
  // console.log('order books:', JSON.stringify(result, null, 2));
  //
  // result = (await getOrderBooks({
  //   ...commonParameters,
  //   marketNames: marketNames,
  // })).body;
  // console.log('order books::', JSON.stringify(result, null, 2));
  //
  // result = (await getOrderBooks({
  //   ...commonParameters
  // })).body;
  // console.log('order books::', JSON.stringify(result, null, 2));

  // result = (await getTickers({
  //   ...commonParameters,
  //   marketName: marketName,
  // })).body;
  // console.log('tickers:', JSON.stringify(result, null, 2));
  //
  // result = (await getTickers({
  //   ...commonParameters,
  //   marketNames: marketNames,
  // })).body;
  // console.log('tickers:', JSON.stringify(result, null, 2));
  //
  // result = (await getTickers({
  //   ...commonParameters
  // })).body;
  // console.log('tickers:', JSON.stringify(result, null, 2));

  result = await createOrders({
    ...commonParameters,
    order: (() => { const order = getNewOrderTemplate(); order.id = orderId; return order; })()
  });
  console.log('orders:', JSON.stringify(result, null, 2));

  result = await createOrders({
    ...commonParameters,
    orders: [
      (() => { const order = getNewOrderTemplate(); order.id = orderIds[0]; return order; })(),
      (() => { const order = getNewOrderTemplate(); order.id = orderIds[1]; return order; })(),
      (() => { const order = getNewOrderTemplate(); order.id = orderIds[2]; return order; })()
    ]
  });
  console.log('orders:', JSON.stringify(result, null, 2));

  // result = await createOrders({
  //   ...commonParameters,
  //   order: getNewOrderTemplate()
  // });
  // console.log('orders:', JSON.stringify(result, null, 2));
});
