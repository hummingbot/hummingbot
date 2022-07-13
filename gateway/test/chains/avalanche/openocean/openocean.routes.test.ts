import request from 'supertest';
import { gatewayApp } from '../../../../src/app';
import { Avalanche } from '../../../../src/chains/avalanche/avalanche';
import { Openocean } from '../../../../src/connectors/openocean/openocean';
import { patchEVMNonceManager } from '../../../evm.nonce.mock';
import { patch, unpatch } from '../../../services/patch';
let avalanche: Avalanche;
let openocean: Openocean;

beforeAll(async () => {
  avalanche = Avalanche.getInstance('avalanche');
  patchEVMNonceManager(avalanche.nonceManager);
  await avalanche.init();

  openocean = Openocean.getInstance('avalanche', 'avalanche');
  await openocean.init();
});

beforeEach(() => {
  patchEVMNonceManager(avalanche.nonceManager);
});

afterEach(() => {
  unpatch();
});

afterAll(async () => {
  await avalanche.close();
});

const patchGetWallet = () => {
  patch(avalanche, 'getWallet', () => {
    return {
      address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
    };
  });
};

const patchStoredTokenList = () => {
  patch(avalanche, 'tokenList', () => {
    return [
      {
        chainId: 43114,
        name: 'USDC',
        symbol: 'USDC',
        address: '0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E',
        decimals: 6,
      },
      {
        chainId: 43114,
        name: 'sAVAX',
        symbol: 'sAVAX',
        address: '0x2b2C81e08f1Af8835a78Bb2A90AE924ACE0eA4bE',
        decimals: 18,
      },
    ];
  });
};

const patchGetTokenBySymbol = () => {
  patch(avalanche, 'getTokenBySymbol', (symbol: string) => {
    if (symbol === 'USDC') {
      return {
        chainId: 43114,
        name: 'USDC',
        symbol: 'USDC',
        address: '0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E',
        decimals: 6,
      };
    } else {
      return {
        chainId: 43114,
        name: 'sAVAX',
        symbol: 'sAVAX',
        address: '0x2b2C81e08f1Af8835a78Bb2A90AE924ACE0eA4bE',
        decimals: 18,
      };
    }
  });
};

const patchGetTokenByAddress = () => {
  patch(openocean, 'getTokenByAddress', () => {
    return {
      chainId: 43114,
      name: 'USDC',
      symbol: 'USDC',
      address: '0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E',
      decimals: 6,
    };
  });
};

const patchGasPrice = () => {
  patch(avalanche, 'gasPrice', () => 100);
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
  patch(avalanche.nonceManager, 'getNonce', () => 21);
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
    await request(gatewayApp)
      .post(`/amm/price`)
      .send({
        chain: 'avalanche',
        network: 'avalanche',
        connector: 'openocean',
        quote: 'sAVAX',
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
    await request(gatewayApp)
      .post(`/amm/price`)
      .send({
        chain: 'avalanche',
        network: 'avalanche',
        connector: 'openocean',
        quote: 'USDC',
        base: 'sAVAX',
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
    patch(avalanche, 'getTokenBySymbol', (symbol: string) => {
      if (symbol === 'WETH') {
        return {
          chainId: 43114,
          name: 'WETH',
          symbol: 'WETH',
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
        chain: 'avalanche',
        network: 'avalanche',
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
    patch(avalanche, 'getTokenBySymbol', (symbol: string) => {
      if (symbol === 'WETH') {
        return {
          chainId: 43114,
          name: 'WETH',
          symbol: 'WETH',
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
        chain: 'avalanche',
        network: 'avalanche',
        connector: 'openocean',
        quote: 'USDC',
        base: 'bDAI',
        amount: '10000',
        side: 'SELL',
      })
      .set('Accept', 'application/json')
      .expect(500);
  });
});
