import request from 'supertest';
import { patch, unpatch } from '../../../services/patch';
import { gatewayApp } from '../../../../src/app';
import { Near } from '../../../../src/chains/near/near';
import { Ref } from '../../../../src/connectors/ref/ref';
let near: Near;
let ref: Ref;

beforeAll(async () => {
  near = Near.getInstance('testnet');
  await near.init();

  ref = Ref.getInstance('near', 'testnet');
  await ref.init();
});

afterEach(() => {
  unpatch();
});

afterAll(async () => {
  await near.close();
});

const address: string = 'test.near';

const patchGetWallet = () => {
  patch(near, 'getWallet', () => {
    return {
      accountId: address,
      connection: {
        networkId: 'testnet',
        signer: {
          getPublicKey: {
            toString: '0xa1242434',
          },
        },
        provider: {},
      },
    };
  });
};

const DAI = {
  spec: 'ft-1.0.0',
  name: 'Dai Stablecoin',
  symbol: 'DAI',
  icon: '',
  reference: '',
  reference_hash: '',
  decimals: 18,
  id: '6b175474e89094c44da98b954eedeac495271d0f.factory.bridge.near',
};

const ETH = {
  decimals: 18,
  icon: '',
  name: 'Ether',
  reference: null,
  reference_hash: null,
  spec: 'ft-1.0.0',
  symbol: 'ETH',
  id: 'aurora',
};

const tradePath = [
  {
    estimate: '438.7318928061755133021873247954861357077652',
    pool: {
      fee: 30,
      gamma_bps: [],
      id: 1207,
      partialAmountIn: '988562670855139614',
      supplies: [Object],
      token0_ref_price: '0',
      tokenIds: [Array],
      Dex: undefined,
      x: '1124497821208300092576',
      y: '501001402176405567560845153269',
    },
    status: 'stableSmart',
    token: {
      decimals: 18,
      icon: 'data:image/png;base64,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',
      name: 'Ether',
      reference: null,
      reference_hash: null,
      spec: 'ft-1.0.0',
      symbol: 'ETH',
      id: 'aurora',
    },
    outputToken: 'wrap.near',
    inputToken: 'aurora',
    nodeRoute: [
      'aurora',
      'wrap.near',
      '6b175474e89094c44da98b954eedeac495271d0f.factory.bridge.near',
    ],
    route: [[Object], [Object]],
    allRoutes: [[Array], [Array]],
    allNodeRoutes: [[Array], [Array]],
    totalInputAmount: '1000000000000000000',
    allAllocations: [[], []],
    tokens: [ETH, DAI],
    routeInputToken: 'aurora',
    routeOutputToken:
      '6b175474e89094c44da98b954eedeac495271d0f.factory.bridge.near',
    overallPriceImpact: '3.53957150694661537802481235958281919791',
  },
  {
    estimate: '1227.5907741995622146029347396525450563115171',
    pool: {
      fee: 30,
      gamma_bps: [],
      id: 2,
      partialAmountIn: '0',
      supplies: [Object],
      token0_ref_price: '0',
      tokenIds: [Array],
      Dex: undefined,
      x: '15490663264513922879112087736',
      y: '44701557151302991680091',
    },
    status: 'stableSmart',
    token: {
      spec: 'ft-1.0.0',
      name: 'Wrapped NEAR fungible token',
      symbol: 'wNEAR',
      icon: null,
      reference: null,
      reference_hash: null,
      decimals: 24,
      id: 'wrap.near',
    },
    outputToken: '6b175474e89094c44da98b954eedeac495271d0f.factory.bridge.near',
    inputToken: 'wrap.near',
    nodeRoute: [
      'aurora',
      'wrap.near',
      '6b175474e89094c44da98b954eedeac495271d0f.factory.bridge.near',
    ],
    route: [[Object], [Object]],
    allRoutes: [[Array], [Array]],
    allNodeRoutes: [[Array], [Array]],
    totalInputAmount: '1000000000000000000',
    allAllocations: [[], []],
    tokens: [ETH, DAI],
    routeInputToken: 'aurora',
    routeOutputToken:
      '6b175474e89094c44da98b954eedeac495271d0f.factory.bridge.near',
    overallPriceImpact: '3.53957150694661537802481235958281919791',
  },
  {
    estimate: '3.8379037803866734449637949018757616354149',
    pool: {
      fee: 19,
      gamma_bps: [],
      id: 3023,
      partialAmountIn: '11437329144860386',
      supplies: [Object],
      token0_ref_price: '0',
      tokenIds: [Array],
      Dex: undefined,
      x: '2282104348405543143',
      y: '771077319322598388824',
    },
    status: 'stableSmart',
    token: {
      decimals: 18,
      icon: 'data:image/png;base64,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',
      name: 'Ether',
      reference: null,
      reference_hash: null,
      spec: 'ft-1.0.0',
      symbol: 'ETH',
      id: 'aurora',
    },
    outputToken: 'marmaj.tkn.near',
    inputToken: 'aurora',
    nodeRoute: [
      'aurora',
      'marmaj.tkn.near',
      '6b175474e89094c44da98b954eedeac495271d0f.factory.bridge.near',
    ],
    route: [[Object], [Object]],
    allRoutes: [[Array], [Array]],
    allNodeRoutes: [[Array], [Array]],
    totalInputAmount: '1000000000000000000',
    allAllocations: [[], []],
    tokens: [ETH, DAI],
    routeInputToken: 'aurora',
    routeOutputToken:
      '6b175474e89094c44da98b954eedeac495271d0f.factory.bridge.near',
    overallPriceImpact: '3.53957150694661537802481235958281919791',
  },
  {
    estimate: '14.299093444897422181731877348671464832746',
    pool: {
      fee: 19,
      gamma_bps: [],
      id: 10,
      partialAmountIn: '0',
      supplies: [Object],
      token0_ref_price: '0',
      tokenIds: [Array],
      Dex: undefined,
      x: '123732450606489839390',
      y: '476173588371142658007',
    },
    status: 'stableSmart',
    token: {
      spec: 'ft-1.0.0',
      name: 'marma j token',
      symbol: 'marmaj',
      icon: 'data:image/jpeg;base64,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',
      reference: null,
      reference_hash: null,
      decimals: 18,
      id: 'marmaj.tkn.near',
    },
    outputToken: '6b175474e89094c44da98b954eedeac495271d0f.factory.bridge.near',
    inputToken: 'marmaj.tkn.near',
    nodeRoute: [
      'aurora',
      'marmaj.tkn.near',
      '6b175474e89094c44da98b954eedeac495271d0f.factory.bridge.near',
    ],
    route: [[Object], [Object]],
    allRoutes: [[Array], [Array]],
    allNodeRoutes: [[Array], [Array]],
    totalInputAmount: '1000000000000000000',
    allAllocations: [[], []],
    tokens: [ETH, DAI],
    routeInputToken: 'aurora',
    routeOutputToken:
      '6b175474e89094c44da98b954eedeac495271d0f.factory.bridge.near',
    overallPriceImpact: '3.53957150694661537802481235958281919791',
  },
];

const patchStoredTokenList = () => {
  patch(near, 'tokenList', () => {
    return [
      {
        chainId: 0,
        decimals: 18,
        icon: '',
        name: 'Ether',
        reference: null,
        reference_hash: null,
        spec: 'ft-1.0.0',
        symbol: 'ETH',
        id: 'aurora',
        address: 'aurora',
      },
      {
        chainId: 0,
        spec: 'ft-1.0.0',
        name: 'Dai Stablecoin',
        symbol: 'DAI',
        icon: '',
        reference: '',
        reference_hash: '',
        decimals: 18,
        id: '6b175474e89094c44da98b954eedeac495271d0f.factory.bridge.near',
        address: '6b175474e89094c44da98b954eedeac495271d0f.factory.bridge.near',
      },
    ];
  });
};

const patchGetTokenBySymbol = () => {
  patch(near, 'getTokenBySymbol', (symbol: string) => {
    if (symbol === 'ETH') {
      return {
        chainId: 0,
        decimals: 18,
        icon: '',
        name: 'Ether',
        reference: null,
        reference_hash: null,
        spec: 'ft-1.0.0',
        symbol: 'ETH',
        id: 'aurora',
        address: 'aurora',
      };
    } else {
      return {
        chainId: 0,
        spec: 'ft-1.0.0',
        name: 'Dai Stablecoin',
        symbol: 'DAI',
        icon: '',
        reference: '',
        reference_hash: '',
        decimals: 18,
        id: '6b175474e89094c44da98b954eedeac495271d0f.factory.bridge.near',
        address: '6b175474e89094c44da98b954eedeac495271d0f.factory.bridge.near',
      };
    }
  });
};

const patchGetTokenByAddress = () => {
  patch(ref, 'getTokenByAddress', () => {
    return {
      chainId: 0,
      spec: 'ft-1.0.0',
      name: 'Dai Stablecoin',
      symbol: 'DAI',
      icon: '',
      reference: '',
      reference_hash: '',
      decimals: 18,
      id: '6b175474e89094c44da98b954eedeac495271d0f.factory.bridge.near',
      address: '6b175474e89094c44da98b954eedeac495271d0f.factory.bridge.near',
    };
  });
};

const patchGasPrice = () => {
  patch(near, 'gasPrice', () => 100);
};

const patchEstimateBuyTrade = () => {
  patch(ref, 'estimateBuyTrade', () => {
    return {
      expectedAmount: '100',
      trade: tradePath,
    };
  });
};

const patchEstimateSellTrade = () => {
  patch(ref, 'estimateSellTrade', () => {
    return {
      expectedAmount: '100',
      trade: tradePath,
    };
  });
};

const patchExecuteTrade = () => {
  patch(ref, 'executeTrade', () => {
    return { hash: '000000000000000' };
  });
};

describe('POST /amm/price', () => {
  it('should return 200 for BUY', async () => {
    patchGetWallet();
    patchStoredTokenList();
    patchGetTokenBySymbol();
    patchGetTokenByAddress();
    patchGasPrice();
    patchEstimateBuyTrade();
    patchExecuteTrade();

    await request(gatewayApp)
      .post(`/amm/price`)
      .send({
        chain: 'near',
        network: 'testnet',
        connector: 'ref',
        quote: 'DAI',
        base: 'ETH',
        amount: '10000',
        side: 'BUY',
      })
      .set('Accept', 'application/json')
      .expect(200)
      .then((res: any) => {
        expect(res.body.amount).toEqual('10000.000000000000000000');
        expect(res.body.rawAmount).toEqual('10000');
      });
  });

  it('should return 200 for SELL', async () => {
    patchGetWallet();
    patchStoredTokenList();
    patchGetTokenBySymbol();
    patchGetTokenByAddress();
    patchGasPrice();
    patchEstimateSellTrade();
    patchExecuteTrade();

    await request(gatewayApp)
      .post(`/amm/price`)
      .send({
        chain: 'near',
        network: 'testnet',
        connector: 'ref',
        quote: 'DAI',
        base: 'ETH',
        amount: '10000',
        side: 'SELL',
      })
      .set('Accept', 'application/json')
      .expect(200)
      .then((res: any) => {
        expect(res.body.amount).toEqual('10000.000000000000000000');
        expect(res.body.rawAmount).toEqual('10000');
      });
  });

  it('should return 500 for unrecognized quote symbol', async () => {
    patchGetWallet();
    patchStoredTokenList();
    patch(near, 'getTokenBySymbol', (symbol: string) => {
      if (symbol === 'ETH') {
        return {
          chainId: 43114,
          name: 'ETH',
          symbol: 'ETH',
          address: '0xd0A1E359811322d97991E03f863a0C30C2cF029C',
          decimals: 18,
        };
      } else {
        return null;
      }
    });
    patchGetTokenByAddress();

    await request(gatewayApp)
      .post(`/amm/price`)
      .send({
        chain: 'near',
        network: 'testnet',
        connector: 'ref',
        quote: 'DOGE',
        base: 'ETH',
        amount: '10000',
        side: 'SELL',
      })
      .set('Accept', 'application/json')
      .expect(500);
  });

  it('should return 500 for unrecognized base symbol', async () => {
    patchGetWallet();
    patchStoredTokenList();
    patch(near, 'getTokenBySymbol', (symbol: string) => {
      if (symbol === 'ETH') {
        return {
          chainId: 43114,
          name: 'ETH',
          symbol: 'ETH',
          address: '0xd0A1E359811322d97991E03f863a0C30C2cF029C',
          decimals: 18,
        };
      } else {
        return null;
      }
    });
    patchGetTokenByAddress();

    await request(gatewayApp)
      .post(`/amm/price`)
      .send({
        chain: 'near',
        network: 'testnet',
        connector: 'ref',
        quote: 'DAI',
        base: 'SHIBA',
        amount: '10000',
        side: 'SELL',
      })
      .set('Accept', 'application/json')
      .expect(500);
  });
});

describe('POST /amm/trade', () => {
  const patchForBuy = () => {
    patchGetWallet();
    patchStoredTokenList();
    patchGetTokenBySymbol();
    patchGetTokenByAddress();
    patchGasPrice();
    patchEstimateBuyTrade();
    patchExecuteTrade();
  };

  it('should return 200 for BUY', async () => {
    patchForBuy();
    await request(gatewayApp)
      .post(`/amm/trade`)
      .send({
        chain: 'near',
        network: 'testnet',
        connector: 'ref',
        quote: 'DAI',
        base: 'ETH',
        amount: '10000',
        address,
        side: 'BUY',
      })
      .set('Accept', 'application/json')
      .expect(200);
  });

  const patchForSell = () => {
    patchGetWallet();
    patchStoredTokenList();
    patchGetTokenBySymbol();
    patchGetTokenByAddress();
    patchGasPrice();
    patchEstimateSellTrade();
    patchExecuteTrade();
  };
  it('should return 200 for SELL', async () => {
    patchForSell();
    await request(gatewayApp)
      .post(`/amm/trade`)
      .send({
        chain: 'near',
        network: 'testnet',
        connector: 'ref',
        quote: 'DAI',
        base: 'ETH',
        amount: '10000',
        address,
        side: 'SELL',
      })
      .set('Accept', 'application/json')
      .expect(200);
  });

  it('should return 404 when parameters are incorrect', async () => {
    await request(gatewayApp)
      .post(`/amm/trade`)
      .send({
        chain: 'near',
        network: 'testnet',
        connector: 'ref',
        quote: 'DAI',
        base: 'ETH',
        amount: 10000,
        address: 'da8',
        side: 'comprar',
      })
      .set('Accept', 'application/json')
      .expect(404);
  });

  it('should return 500 when base token is unknown', async () => {
    patchForSell();
    patch(near, 'getTokenBySymbol', (symbol: string) => {
      if (symbol === 'ETH') {
        return {
          chainId: 43114,
          name: 'ETH',
          symbol: 'ETH',
          address: '0xd0A1E359811322d97991E03f863a0C30C2cF029C',
          decimals: 18,
        };
      } else {
        return null;
      }
    });

    await request(gatewayApp)
      .post(`/amm/trade`)
      .send({
        chain: 'near',
        network: 'testnet',
        connector: 'ref',
        quote: 'ETH',
        base: 'BITCOIN',
        amount: '10000',
        address,
        side: 'BUY',
      })
      .set('Accept', 'application/json')
      .expect(500);
  });

  it('should return 500 when quote token is unknown', async () => {
    patchForSell();
    patch(near, 'getTokenBySymbol', (symbol: string) => {
      if (symbol === 'ETH') {
        return {
          chainId: 43114,
          name: 'ETH',
          symbol: 'ETH',
          address: '0xd0A1E359811322d97991E03f863a0C30C2cF029C',
          decimals: 18,
        };
      } else {
        return null;
      }
    });

    await request(gatewayApp)
      .post(`/amm/trade`)
      .send({
        chain: 'near',
        network: 'testnet',
        connector: 'ref',
        quote: 'BITCOIN',
        base: 'ETH',
        amount: '10000',
        address,
        side: 'BUY',
      })
      .set('Accept', 'application/json')
      .expect(500);
  });

  it('should return 200 for SELL with limitPrice', async () => {
    patchForSell();
    await request(gatewayApp)
      .post(`/amm/trade`)
      .send({
        chain: 'near',
        network: 'testnet',
        connector: 'ref',
        quote: 'DAI',
        base: 'ETH',
        amount: '10000',
        address,
        side: 'SELL',
        limitPrice: '9',
      })
      .set('Accept', 'application/json')
      .expect(200);
  });

  it('should return 200 for BUY with limitPrice', async () => {
    patchForBuy();
    await request(gatewayApp)
      .post(`/amm/trade`)
      .send({
        chain: 'near',
        network: 'testnet',
        connector: 'ref',
        quote: 'DAI',
        base: 'ETH',
        amount: '10000',
        address,
        side: 'BUY',
        limitPrice: '999999999999999999999',
      })
      .set('Accept', 'application/json')
      .expect(200);
  });

  it('should return 500 for SELL with price lower than limitPrice', async () => {
    patchForSell();
    await request(gatewayApp)
      .post(`/amm/trade`)
      .send({
        chain: 'near',
        network: 'testnet',
        connector: 'ref',
        quote: 'DAI',
        base: 'ETH',
        amount: '10000',
        address,
        side: 'SELL',
        limitPrice: '99999999999',
      })
      .set('Accept', 'application/json')
      .expect(500);
  });

  it('should return 500 for BUY with price higher than limitPrice', async () => {
    patchForBuy();
    await request(gatewayApp)
      .post(`/amm/trade`)
      .send({
        chain: 'near',
        network: 'testnet',
        connector: 'ref',
        quote: 'DAI',
        base: 'ETH',
        amount: '10000',
        address,
        side: 'BUY',
        limitPrice: '0',
      })
      .set('Accept', 'application/json')
      .expect(500);
  });
});

describe('POST /amm/estimateGas', () => {
  it('should return 200 for valid connector', async () => {
    patchGasPrice();

    await request(gatewayApp)
      .post('/amm/estimateGas')
      .send({
        chain: 'near',
        network: 'testnet',
        connector: 'ref',
      })
      .set('Accept', 'application/json')
      .expect(200)
      .then((res: any) => {
        expect(res.body.network).toEqual('testnet');
        expect(res.body.gasPrice).toEqual(100);
        expect(res.body.gasCost).toEqual(
          String((100 * ref.gasLimitEstimate) / 1e24)
        );
      });
  });
});
