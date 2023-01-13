import request from 'supertest';
import { Harmony } from '../../../../src/chains/harmony/harmony';
import { Openocean } from '../../../../src/connectors/openocean/openocean';
import { patchEVMNonceManager } from '../../../evm.nonce.mock';
import { patch, unpatch } from '../../../services/patch';
import { gasCostInEthString } from '../../../../src/services/base';
import { AmmRoutes } from '../../../../src/amm/amm.routes';
import express from 'express';
import { Express } from 'express-serve-static-core';
let app: Express;
let harmony: Harmony;
let openocean: Openocean;

beforeAll(async () => {
  app = express();
  app.use(express.json());

  harmony = Harmony.getInstance('mainnet');
  patchEVMNonceManager(harmony.nonceManager);
  await harmony.init();

  openocean = Openocean.getInstance('harmony', 'mainnet');
  await openocean.init();

  app.use('/amm', AmmRoutes.router);
});

beforeEach(() => {
  patchEVMNonceManager(harmony.nonceManager);
});

afterEach(() => {
  unpatch();
});

afterAll(async () => {
  await harmony.close();
});

const address: string = '0xFaA12FD102FE8623C9299c72B03E45107F2772B5';

const patchGetWallet = () => {
  patch(harmony, 'getWallet', () => {
    return {
      address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
    };
  });
};

const patchInit = () => {
  patch(openocean, 'init', async () => {
    return;
  });
};

const patchStoredTokenList = () => {
  patch(harmony, 'tokenList', () => {
    return [
      {
        chainId: 1666600000,
        name: 'USDC',
        symbol: '1USDC',
        address: '0x985458e523db3d53125813ed68c274899e9dfab4',
        decimals: 6,
      },
      {
        chainId: 1666600000,
        name: 'DAI',
        symbol: '1DAI',
        address: '0xef977d2f931c1978db5f6747666fa1eacb0d0339',
        decimals: 18,
      },
    ];
  });
};

const patchGetTokenBySymbol = () => {
  patch(harmony, 'getTokenBySymbol', (symbol: string) => {
    if (symbol === 'USDC') {
      return {
        chainId: 1666600000,
        name: 'USDC',
        symbol: '1USDC',
        address: '0x985458e523db3d53125813ed68c274899e9dfab4',
        decimals: 6,
      };
    } else {
      return {
        chainId: 1666600000,
        name: 'DAI',
        symbol: '1DAI',
        address: '0xef977d2f931c1978db5f6747666fa1eacb0d0339',
        decimals: 18,
      };
    }
  });
};

const patchGetTokenByAddress = () => {
  patch(openocean, 'getTokenByAddress', () => {
    return {
      chainId: 1666600000,
      name: 'USDC',
      symbol: '1USDC',
      address: '0x985458e523db3d53125813ed68c274899e9dfab4',
      decimals: 6,
    };
  });
};

const patchGasPrice = () => {
  patch(harmony, 'gasPrice', () => 100);
};

const patchEstimateBuyTrade = () => {
  patch(openocean, 'estimateBuyTrade', () => {
    return {
      expectedAmount: {
        toSignificant: () => 100,
      },
      trade: {
        executionPrice: {
          invert: jest.fn().mockReturnValue({
            toSignificant: () => 100,
            toFixed: () => '100',
          }),
        },
      },
    };
  });
};

const patchEstimateSellTrade = () => {
  patch(openocean, 'estimateSellTrade', () => {
    return {
      expectedAmount: {
        toSignificant: () => 100,
      },
      trade: {
        executionPrice: {
          toSignificant: () => 100,
          toFixed: () => '100',
        },
      },
    };
  });
};

const patchGetNonce = () => {
  patch(harmony.nonceManager, 'getNonce', () => 21);
};

const patchExecuteTrade = () => {
  patch(openocean, 'executeTrade', () => {
    return { nonce: 21, hash: '000000000000000' };
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
    patchGetNonce();
    patchExecuteTrade();
    await request(app)
      .post(`/amm/price`)
      .send({
        chain: 'harmony',
        network: 'mainnet',
        connector: 'openocean',
        quote: 'DAI',
        base: 'USDC',
        amount: '0.01',
        side: 'BUY',
      })
      .set('Accept', 'application/json')
      .expect(200)
      .then((res: any) => {
        expect(res.body.amount).toEqual('0.010000');
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
    patchGetNonce();
    patchExecuteTrade();
    await request(app)
      .post(`/amm/price`)
      .send({
        chain: 'harmony',
        network: 'mainnet',
        connector: 'openocean',
        quote: 'USDC',
        base: 'DAI',
        amount: '10000',
        side: 'SELL',
      })
      .set('Accept', 'application/json')
      .expect(200)
      .then((res: any) => {
        expect(res.body.amount).toEqual('10000.000000');
        expect(res.body.rawAmount).toEqual('10000000000');
      });
  });

  it('should return 500 for unrecognized quote symbol', async () => {
    patchGetWallet();
    patchStoredTokenList();
    patch(harmony, 'getTokenBySymbol', (symbol: string) => {
      if (symbol === 'WETH') {
        return {
          chainId: 1666600000,
          name: 'WETH',
          symbol: '1WETH',
          address: '0xf720b7910c6b2ff5bd167171ada211e226740bfe',
          decimals: 18,
        };
      } else {
        return null;
      }
    });
    patchGetTokenByAddress();
    await request(app)
      .post(`/amm/price`)
      .send({
        chain: 'harmony',
        network: 'mainnet',
        connector: 'openocean',
        quote: 'USDC',
        base: 'bDAI',
        amount: '10000',
        side: 'SELL',
      })
      .set('Accept', 'application/json')
      .expect(500);
  });

  it('should return 500 for unrecognized base symbol', async () => {
    patchGetWallet();
    patchStoredTokenList();
    patch(harmony, 'getTokenBySymbol', (symbol: string) => {
      if (symbol === 'WETH') {
        return {
          chainId: 1666600000,
          name: 'WETH',
          symbol: '1WETH',
          address: '0xf720b7910c6b2ff5bd167171ada211e226740bfe',
          decimals: 18,
        };
      } else {
        return null;
      }
    });
    patchGetTokenByAddress();
    await request(app)
      .post(`/amm/price`)
      .send({
        chain: 'harmony',
        network: 'mainnet',
        connector: 'openocean',
        quote: 'USDC',
        base: 'bDAI',
        amount: '10000',
        side: 'SELL',
      })
      .set('Accept', 'application/json')
      .expect(500);
  });

  it('should return 500 for unrecognized base symbol with decimals in the amount and SELL', async () => {
    patchGetWallet();
    patchInit();
    patchStoredTokenList();
    patchGetTokenBySymbol();
    patchGetTokenByAddress();

    await request(app)
      .post(`/amm/price`)
      .send({
        chain: 'harmony',
        network: 'mainnet',
        connector: 'openocean',
        quote: 'USDC',
        base: 'bDAI',
        amount: '10.000',
        side: 'SELL',
      })
      .set('Accept', 'application/json')
      .expect(500);
  });

  it('should return 500 for unrecognized base symbol with decimals in the amount and BUY', async () => {
    patchGetWallet();
    patchInit();
    patchStoredTokenList();
    patchGetTokenBySymbol();
    patchGetTokenByAddress();

    await request(app)
      .post(`/amm/price`)
      .send({
        chain: 'harmony',
        network: 'mainnet',
        connector: 'openocean',
        quote: 'USDC',
        base: 'bDAI',
        amount: '10.000',
        side: 'BUY',
      })
      .set('Accept', 'application/json')
      .expect(500);
  });

  it('should return 500 when the priceSwapIn operation fails', async () => {
    patchGetWallet();
    patchInit();
    patchStoredTokenList();
    patchGetTokenBySymbol();
    patchGetTokenByAddress();
    patch(openocean, 'priceSwapIn', () => {
      return 'error';
    });

    await request(app)
      .post(`/amm/price`)
      .send({
        chain: 'harmony',
        network: 'mainnet',
        connector: 'openocean',
        quote: 'USDC',
        base: 'bDAI',
        amount: '10000',
        side: 'SELL',
      })
      .set('Accept', 'application/json')
      .expect(500);
  });

  it('should return 500 when the priceSwapOut operation fails', async () => {
    patchGetWallet();
    patchInit();
    patchStoredTokenList();
    patchGetTokenBySymbol();
    patchGetTokenByAddress();
    patch(openocean, 'priceSwapOut', () => {
      return 'error';
    });

    await request(app)
      .post(`/amm/price`)
      .send({
        chain: 'harmony',
        network: 'mainnet',
        connector: 'openocean',
        quote: 'USDC',
        base: 'bDAI',
        amount: '10000',
        side: 'BUY',
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
    patchGetNonce();
    patchExecuteTrade();
  };
  it('should return 200 for BUY', async () => {
    patchForBuy();
    await request(app)
      .post(`/amm/trade`)
      .send({
        chain: 'harmony',
        network: 'mainnet',
        connector: 'openocean',
        quote: 'DAI',
        base: 'USDC',
        amount: '0.01',
        address,
        side: 'BUY',
        nonce: 21,
      })
      .set('Accept', 'application/json')
      .expect(200)
      .then((res: any) => {
        expect(res.body.nonce).toEqual(21);
      });
  });

  it('should return 200 for BUY without nonce parameter', async () => {
    patchForBuy();
    await request(app)
      .post(`/amm/trade`)
      .send({
        chain: 'harmony',
        network: 'mainnet',
        connector: 'openocean',
        quote: 'DAI',
        base: 'USDC',
        amount: '0.01',
        address,
        side: 'BUY',
      })
      .set('Accept', 'application/json')
      .expect(200);
  });

  it('should return 200 for BUY with maxFeePerGas and maxPriorityFeePerGas', async () => {
    patchForBuy();
    await request(app)
      .post(`/amm/trade`)
      .send({
        chain: 'harmony',
        network: 'mainnet',
        connector: 'openocean',
        quote: 'DAI',
        base: 'USDC',
        amount: '0.01',
        address,
        side: 'BUY',
        nonce: 21,
        maxFeePerGas: '5000000000',
        maxPriorityFeePerGas: '5000000000',
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
    patchGetNonce();
    patchExecuteTrade();
  };
  it('should return 200 for SELL', async () => {
    patchForSell();
    await request(app)
      .post(`/amm/trade`)
      .send({
        chain: 'harmony',
        network: 'mainnet',
        connector: 'openocean',
        quote: 'USDC',
        base: 'DAI',
        amount: '10000',
        address,
        side: 'SELL',
        nonce: 21,
      })
      .set('Accept', 'application/json')
      .expect(200)
      .then((res: any) => {
        expect(res.body.nonce).toEqual(21);
      });
  });

  it('should return 200 for SELL  with maxFeePerGas and maxPriorityFeePerGas', async () => {
    patchForSell();
    await request(app)
      .post(`/amm/trade`)
      .send({
        chain: 'harmony',
        network: 'mainnet',
        connector: 'openocean',
        quote: 'USDC',
        base: 'DAI',
        amount: '10000',
        address,
        side: 'SELL',
        nonce: 21,
        maxFeePerGas: '5000000000',
        maxPriorityFeePerGas: '5000000000',
      })
      .set('Accept', 'application/json')
      .expect(200);
  });

  it('should return 404 when parameters are incorrect', async () => {
    await request(app)
      .post(`/amm/trade`)
      .send({
        chain: 'harmony',
        network: 'mainnet',
        connector: 'openocean',
        quote: 'USDC',
        base: 'DAI',
        amount: 10000,
        address: 'da8',
        side: 'comprar',
      })
      .set('Accept', 'application/json')
      .expect(404);
  });

  it('should return 500 when base token is unknown', async () => {
    patchForSell();
    patch(harmony, 'getTokenBySymbol', (symbol: string) => {
      if (symbol === 'USDC') {
        return {
          chainId: 43114,
          name: 'USDC',
          symbol: '1USDC',
          address: '0x985458e523db3d53125813ed68c274899e9dfab4',
          decimals: 6,
        };
      } else {
        return null;
      }
    });

    await request(app)
      .post(`/amm/trade`)
      .send({
        chain: 'harmony',
        network: 'mainnet',
        connector: 'openocean',
        quote: 'USDC',
        base: 'BITCOIN',
        amount: '10000',
        address,
        side: 'BUY',
        nonce: 21,
        maxFeePerGas: '5000000000',
        maxPriorityFeePerGas: '5000000000',
      })
      .set('Accept', 'application/json')
      .expect(500);
  });

  it('should return 500 when quote token is unknown', async () => {
    patchForSell();
    patch(harmony, 'getTokenBySymbol', (symbol: string) => {
      if (symbol === 'USDC') {
        return {
          chainId: 43114,
          name: 'USDC',
          symbol: '1USDC',
          address: '0x985458e523db3d53125813ed68c274899e9dfab4',
          decimals: 6,
        };
      } else {
        return null;
      }
    });

    await request(app)
      .post(`/amm/trade`)
      .send({
        chain: 'harmony',
        network: 'mainnet',
        connector: 'openocean',
        quote: 'BITCOIN',
        base: 'USDC',
        amount: '10000',
        address,
        side: 'BUY',
        nonce: 21,
        maxFeePerGas: '5000000000',
        maxPriorityFeePerGas: '5000000000',
      })
      .set('Accept', 'application/json')
      .expect(500);
  });

  it('should return 200 for SELL with limitPrice', async () => {
    patchForSell();
    await request(app)
      .post(`/amm/trade`)
      .send({
        chain: 'harmony',
        network: 'mainnet',
        connector: 'openocean',
        quote: 'USDC',
        base: 'DAI',
        amount: '10000',
        address,
        side: 'SELL',
        nonce: 21,
        limitPrice: '9',
      })
      .set('Accept', 'application/json')
      .expect(200);
  });

  it('should return 200 for BUY with limitPrice', async () => {
    patchForBuy();
    await request(app)
      .post(`/amm/trade`)
      .send({
        chain: 'harmony',
        network: 'mainnet',
        connector: 'openocean',
        quote: 'DAI',
        base: 'USDC',
        amount: '0.01',
        address,
        side: 'BUY',
        nonce: 21,
        limitPrice: '999999999999999999999',
      })
      .set('Accept', 'application/json')
      .expect(200);
  });

  it('should return 200 for SELL with price higher than limitPrice', async () => {
    patchForSell();
    await request(app)
      .post(`/amm/trade`)
      .send({
        chain: 'harmony',
        network: 'mainnet',
        connector: 'openocean',
        quote: 'USDC',
        base: 'DAI',
        amount: '10000',
        address,
        side: 'SELL',
        nonce: 21,
        limitPrice: '99999999999',
      })
      .set('Accept', 'application/json')
      .expect(500);
  });

  it('should return 200 for BUY with price less than limitPrice', async () => {
    patchForBuy();
    await request(app)
      .post(`/amm/trade`)
      .send({
        chain: 'harmony',
        network: 'mainnet',
        connector: 'openocean',
        quote: 'DAI',
        base: 'USDC',
        amount: '0.01',
        address,
        side: 'BUY',
        nonce: 21,
        limitPrice: '9',
      })
      .set('Accept', 'application/json')
      .expect(500);
  });
});

describe('POST /amm/estimateGas', () => {
  it('should return 200 for valid connector', async () => {
    patchInit();
    patchGasPrice();

    await request(app)
      .post('/amm/estimateGas')
      .send({
        chain: 'harmony',
        network: 'mainnet',
        connector: 'openocean',
      })
      .set('Accept', 'application/json')
      .expect(200)
      .then((res: any) => {
        expect(res.body.network).toEqual('mainnet');
        expect(res.body.gasPrice).toEqual(100);
        expect(res.body.gasCost).toEqual(
          gasCostInEthString(100, openocean.gasLimitEstimate)
        );
      });
  });

  it('should return 500 for invalid connector', async () => {
    patchInit();
    patchGasPrice();

    await request(app)
      .post('/amm/estimateGas')
      .send({
        chain: 'harmony',
        network: 'mainnet',
        connector: 'pangolin',
      })
      .set('Accept', 'application/json')
      .expect(500);
  });
});
