import 'jest-extended';
import { Solana } from '../../../src/chains/solana/solana';
import { Serum } from '../../../src/connectors/serum/serum';
import {
  cancelOrders,
  createOrders,
  getFilledOrders,
  getMarkets,
  getOpenOrders,
  getOrderBooks,
  getOrders,
  getTickers,
  settleFunds,
} from '../../../src/connectors/serum/serum.controllers';
import { default as config } from '../../connectors/serum/fixtures/serumConfig';
import { unpatch } from '../../services/patch';
import { getNewOrderTemplate } from './fixtures/dummy';
import { default as patchesCreator } from './fixtures/patches/patches';

jest.setTimeout(1000000);

let solana: Solana;
let serum: Serum;

let patches: Map<string, any>;

beforeAll(async () => {
  solana = await Solana.getInstance(config.serum.network);

  serum = await Serum.getInstance(config.serum.chain, config.serum.network);

  patches = patchesCreator(solana, serum);

  patches.get('solana/init')();
  patches.get('serum/init')();

  patches.get('solana/ready')();
  patches.get('serum/ready')();

  patches.get('serum/serumGetMarketsInformation')();

  await solana.init();
  await serum.init();
});

afterEach(() => {
  unpatch();
});

const commonParameters = {
  chain: config.serum.chain,
  network: config.serum.network,
  connector: config.serum.connector,
};

const marketNames = ['SOL/USDT', 'SOL/USDC'];

describe('Full Flow', () => {
  /*
  create order [0]
  create orders [1, 2, 3, 4, 5, 6, 7]
  get open order [0]
  get order [1]
  get open orders [2, 3]
  get orders [4, 5]
  get all open orders (0, 1, 2, 3, 4, 5, 6, 7)
  get all orders (0, 1, 2, 3, 4, 5, 6, 7)
  cancel open order [0]
  cancel order [1]
  get canceled open order [0]
  get canceled order [1]
  get filled order [2]
  get filled orders [3, 4]
  get all filled orders (),
  cancel open orders [2, 3]
  cancel orders [4, 5]
  get canceled open orders [2, 3]
  get canceled orders [4, 5]
  cancel all open orders (6, 7)
  get all open orders ()
  get all orders ()
  create orders [8, 9]
  get all open orders ()
  get all orders ()
  cancel all orders (8, 9)
  get all open orders ()
  get all orders ()
  settle funds for market [SOL/USDT]
  settle funds for markets [SOL/USDT, SOL/USDC]
  settle all funds (SOL/USDT, SOL/USDC, SRM/SOL)
  */

  const marketName = marketNames[0];

  const orderIds = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'];

  let request: any;

  let response: any;

  it('getMarket ["SOL/USDT"]', async () => {
    request = {
      ...commonParameters,
      name: marketName,
    };
    response = await getMarkets(solana, serum, request);
  });

  it('getMarkets ["SOL/USDT", "SOL/USDC"]', async () => {
    request = {
      ...commonParameters,
      names: marketNames,
    };
    response = await getMarkets(solana, serum, request);
  });

  it('getMarkets (all)', async () => {
    request = {
      ...commonParameters,
    };
    response = await getMarkets(solana, serum, request);
  });

  it('getOrderBook ["SOL/USDT"]', async () => {
    request = {
      ...commonParameters,
      marketName: marketName,
    };
    response = await getOrderBooks(solana, serum, request);
  });

  it('getOrderBooks ["SOL/USDT", "SOL/USDC"]', async () => {
    request = {
      ...commonParameters,
      marketNames: marketNames,
    };
    response = await getOrderBooks(solana, serum, request);
  });

  it('getOrderBooks (all)', async () => {
    request = {
      ...commonParameters,
    };
    response = await getOrderBooks(solana, serum, request);
  });

  it('getTicker ["SOL/USDT"]', async () => {
    patches.get('serum/getTicker')('SOL/USDT');

    request = {
      ...commonParameters,
      marketName: marketName,
    };
    response = await getTickers(solana, serum, request);
  });

  it('getTickers ["SOL/USDT", "SOL/USDC"]', async () => {
    request = {
      ...commonParameters,
      marketNames: marketNames,
    };
    response = await getTickers(solana, serum, request);
  });

  it('getTickers (all)', async () => {
    request = {
      ...commonParameters,
    };
    response = await getTickers(solana, serum, request);
  });

  it('cancelOrders (all)', async () => {
    patches.get('solana/getKeyPair')();
    patches.get('serum/serumMarketCancelOrdersAndSettleFunds')();

    request = {
      ...commonParameters,
      ownerAddress: config.solana.wallet.owner.publicKey,
    };
    response = await cancelOrders(solana, serum, request);
  });

  // it('settleFunds (all)', async () => {
  //   request = {
  //     ...commonParameters,
  //     ownerAddress: config.solana.wallet.owner.address,
  //   };
  //   response = await settleFunds(solana, serum, request);
  //   console.log('settle all funds', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));
  // });

  it('getOpenOrders (all)', async () => {
    patches.get('solana/getKeyPair')();

    request = {
      ...commonParameters,
      ownerAddress: config.solana.wallet.owner.publicKey,
    };
    response = await getOpenOrders(solana, serum, request);
  });

  it('createOrder [0]', async () => {
    // patches.get('solana/getKeyPair')();
    // patches.get('serum/serumMarketPlaceOrders')();

    request = {
      ...commonParameters,
      order: (() => {
        const order = getNewOrderTemplate();
        order.id = orderIds[0];
        return order;
      })(),
    };
    response = await createOrders(solana, serum, request);
  });

  it('createOrders [1, 2, 3, 4, 5, 6, 7]', async () => {
    // patches.get('solana/getKeyPair')();
    // patches.get('serum/serumMarketPlaceOrders')();

    request = {
      ...commonParameters,
      orders: [
        (() => {
          const order = getNewOrderTemplate();
          order.id = orderIds[1];
          return order;
        })(),
        (() => {
          const order = getNewOrderTemplate();
          order.id = orderIds[2];
          return order;
        })(),
        (() => {
          const order = getNewOrderTemplate();
          order.id = orderIds[3];
          return order;
        })(),
        (() => {
          const order = getNewOrderTemplate();
          order.id = orderIds[4];
          return order;
        })(),
        (() => {
          const order = getNewOrderTemplate();
          order.id = orderIds[5];
          return order;
        })(),
        (() => {
          const order = getNewOrderTemplate();
          order.id = orderIds[6];
          return order;
        })(),
        (() => {
          const order = getNewOrderTemplate();
          order.id = orderIds[7];
          return order;
        })(),
        // (() => { const order = getNewOrderTemplate(); order.id = orderIds[8]; return order; })(),
      ],
    };
    response = await createOrders(solana, serum, request);
  });

  it('getOpenOrder [0]', async () => {
    patches.get('solana/getKeyPair')();

    request = {
      ...commonParameters,
      order: {
        id: orderIds[0],
        ownerAddress: config.solana.wallet.owner.publicKey,
      },
    };
    response = await getOpenOrders(solana, serum, request);
  });

  it('getOrder [1]', async () => {
    patches.get('solana/getKeyPair')();

    request = {
      ...commonParameters,
      order: {
        id: orderIds[1],
        ownerAddress: config.solana.wallet.owner.publicKey,
      },
    };
    response = await getOrders(solana, serum, request);
  });

  it('getOpenOrders [2, 3]', async () => {
    patches.get('solana/getKeyPair')();

    request = {
      ...commonParameters,
      orders: [
        {
          ids: orderIds.slice(2, 4),
          ownerAddress: config.solana.wallet.owner.publicKey,
        },
      ],
    };
    response = await getOpenOrders(solana, serum, request);
  });

  it('getOrders [3, 4]', async () => {
    patches.get('solana/getKeyPair')();

    request = {
      ...commonParameters,
      orders: [
        {
          ids: orderIds.slice(4, 6),
          ownerAddress: config.solana.wallet.owner.publicKey,
        },
      ],
    };
    response = await getOrders(solana, serum, request);
  });

  it('getOpenOrders (all)', async () => {
    patches.get('solana/getKeyPair')();

    request = {
      ...commonParameters,
      ownerAddress: config.solana.wallet.owner.publicKey,
    };
    response = await getOpenOrders(solana, serum, request);
  });

  it('getOrders (all)', async () => {
    patches.get('solana/getKeyPair')();

    request = {
      ...commonParameters,
      ownerAddress: config.solana.wallet.owner.publicKey,
    };
    response = await getOrders(solana, serum, request);
  });

  it('cancelOrders [0]', async () => {
    patches.get('solana/getKeyPair')();
    patches.get('serum/serumMarketCancelOrdersAndSettleFunds')();

    request = {
      ...commonParameters,
      order: {
        id: orderIds[0],
        ownerAddress: config.solana.wallet.owner.publicKey,
        marketName: marketName,
      },
    };
    response = await cancelOrders(solana, serum, request);
  });

  it('cancelOrders [1]', async () => {
    patches.get('solana/getKeyPair')();
    patches.get('serum/serumMarketCancelOrdersAndSettleFunds')();

    request = {
      ...commonParameters,
      order: {
        id: orderIds[1],
        ownerAddress: config.solana.wallet.owner.publicKey,
        marketName: marketName,
      },
    };
    response = await cancelOrders(solana, serum, request);
  });

  // it('getOpenOrders [0]', async () => {
  //   request = {
  //     ...commonParameters,
  //     order: {
  //       id: orderIds[0],
  //       ownerAddress: config.solana.wallet.owner.address
  //     },
  //   };
  //   response = await getOpenOrders(solana, serum, request);
  //   console.log('get open order', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));
  // });

  // it('getOrders [1]', async () => {
  //   request = {
  //     ...commonParameters,
  //     order: {
  //       id: orderIds[1],
  //       ownerAddress: config.solana.wallet.owner.address
  //     },
  //   };
  //   response = await getOrders(solana, serum, request);
  //   console.log('get order', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));
  // });

  // it('getFilledOrders [2]', async () => {
  //   request = {
  //     ...commonParameters,
  //     order: {
  //       id: orderIds[2],
  //       ownerAddress: config.solana.wallet.owner.address,
  //     },
  //   };
  //   response = await getFilledOrders(solana, serum, request);
  //   console.log(
  //     'get filled order',
  //     'request:',
  //     JSON.stringify(request, null, 2),
  //     'response',
  //     JSON.stringify(response, null, 2)
  //   );
  // });
  //
  // it('getFilledOrders [3, 4]', async () => {
  //   request = {
  //     ...commonParameters,
  //     orders: [
  //       {
  //         ids: orderIds.slice(3, 5),
  //         ownerAddress: config.solana.wallet.owner.address,
  //       },
  //     ],
  //   };
  //   response = await getFilledOrders(solana, serum, request);
  //   console.log(
  //     'get filled orders',
  //     'request:',
  //     JSON.stringify(request, null, 2),
  //     'response',
  //     JSON.stringify(response, null, 2)
  //   );
  // });

  it('getFilledOrders (all)', async () => {
    patches.get('solana/getKeyPair')();

    request = {
      ...commonParameters,
      ownerAddress: config.solana.wallet.owner.publicKey,
    };
    response = await getFilledOrders(solana, serum, request);
  });

  it('cancelOrders [2, 3]', async () => {
    patches.get('solana/getKeyPair')();
    patches.get('serum/serumMarketCancelOrdersAndSettleFunds')();

    request = {
      ...commonParameters,
      orders: [
        {
          ids: orderIds.slice(2, 4),
          ownerAddress: config.solana.wallet.owner.publicKey,
          marketName: marketName,
        },
      ],
    };
    response = await cancelOrders(solana, serum, request);
  });

  it('cancelOrders [4, 5]', async () => {
    patches.get('solana/getKeyPair')();
    patches.get('serum/serumMarketCancelOrdersAndSettleFunds')();

    request = {
      ...commonParameters,
      orders: [
        {
          ids: orderIds.slice(4, 6),
          ownerAddress: config.solana.wallet.owner.publicKey,
          marketName: marketName,
        },
      ],
    };
    response = await cancelOrders(solana, serum, request);
  });

  it('getOpenOrders [2, 3]', async () => {
    patches.get('solana/getKeyPair')();

    request = {
      ...commonParameters,
      orders: [
        {
          ids: orderIds.slice(2, 4),
          ownerAddress: config.solana.wallet.owner.publicKey,
        },
      ],
    };
    response = await getOpenOrders(solana, serum, request);
  });

  it('getOrders [4, 5]', async () => {
    patches.get('solana/getKeyPair')();

    request = {
      ...commonParameters,
      orders: [
        {
          ids: orderIds.slice(4, 6),
          ownerAddress: config.solana.wallet.owner.publicKey,
        },
      ],
    };
    response = await getOrders(solana, serum, request);
  });

  it('cancelOrders (all)', async () => {
    patches.get('solana/getKeyPair')();
    patches.get('serum/serumMarketCancelOrdersAndSettleFunds')();

    request = {
      ...commonParameters,
      ownerAddress: config.solana.wallet.owner.publicKey,
    };
    response = await cancelOrders(solana, serum, request);
  });

  it('getOpenOrders (all)', async () => {
    patches.get('solana/getKeyPair')();

    request = {
      ...commonParameters,
      ownerAddress: config.solana.wallet.owner.publicKey,
    };
    response = await getOpenOrders(solana, serum, request);
  });

  it('getOrders (all)', async () => {
    patches.get('solana/getKeyPair')();

    request = {
      ...commonParameters,
      ownerAddress: config.solana.wallet.owner.publicKey,
    };
    response = await getOrders(solana, serum, request);
  });

  it('createOrders [8, 9]', async () => {
    patches.get('solana/getKeyPair')();

    request = {
      ...commonParameters,
      orders: [
        (() => {
          const order = getNewOrderTemplate();
          order.id = orderIds[8];
          return order;
        })(),
        (() => {
          const order = getNewOrderTemplate();
          order.id = orderIds[9];
          return order;
        })(),
      ],
    };
    response = await createOrders(solana, serum, request);
  });

  it('getOpenOrders (all)', async () => {
    patches.get('solana/getKeyPair')();

    request = {
      ...commonParameters,
      ownerAddress: config.solana.wallet.owner.publicKey,
    };
    response = await getOpenOrders(solana, serum, request);
  });

  it('getOrders (all)', async () => {
    patches.get('solana/getKeyPair')();

    request = {
      ...commonParameters,
      ownerAddress: config.solana.wallet.owner.publicKey,
    };
    response = await getOrders(solana, serum, request);
  });

  it('cancelOrders (all)', async () => {
    patches.get('solana/getKeyPair')();
    patches.get('serum/serumMarketCancelOrdersAndSettleFunds')();

    request = {
      ...commonParameters,
      ownerAddress: config.solana.wallet.owner.publicKey,
    };
    response = await cancelOrders(solana, serum, request);
  });

  it('getOpenOrders (all)', async () => {
    patches.get('solana/getKeyPair')();

    request = {
      ...commonParameters,
      ownerAddress: config.solana.wallet.owner.publicKey,
    };
    response = await getOpenOrders(solana, serum, request);
  });

  it('getOrders (all)', async () => {
    patches.get('solana/getKeyPair')();

    request = {
      ...commonParameters,
      ownerAddress: config.solana.wallet.owner.publicKey,
    };
    response = await getOrders(solana, serum, request);
  });

  it('settleFunds ["SOL/USDT"]', async () => {
    patches.get('solana/getKeyPair')();
    patches.get('serum/serumSettleSeveralFunds')();

    request = {
      ...commonParameters,
      marketName: marketName,
      ownerAddress: config.solana.wallet.owner.publicKey,
    };
    response = await settleFunds(solana, serum, request);
  });

  it('settleFunds ["SOL/USDT", "SOL/USDC"]', async () => {
    patches.get('solana/getKeyPair')();
    patches.get('serum/serumSettleSeveralFunds')();

    request = {
      ...commonParameters,
      marketNames: marketNames,
      ownerAddress: config.solana.wallet.owner.publicKey,
    };
    response = await settleFunds(solana, serum, request);
  });

  it('settleFunds (all)', async () => {
    patches.get('solana/getKeyPair')();
    patches.get('serum/serumSettleSeveralFunds')();

    request = {
      ...commonParameters,
      ownerAddress: config.solana.wallet.owner.publicKey,
    };
    response = await settleFunds(solana, serum, request);
  });

  expect(response);
});
