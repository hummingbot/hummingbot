import express from 'express';
import { Express } from 'express-serve-static-core';
import request from 'supertest';
import { UniswapRoutes } from '../../../../src/chains/ethereum/uniswap/uniswap.routes';
import { ConfigManager } from '../../../../src/services/config-manager';
import { patch, unpatch } from '../../../services/patch';

let app: Express;

beforeAll(async () => {
  app = express();
  app.use(express.json());
  app.use('/eth/uniswap', UniswapRoutes.router);
});

afterEach(() => {
  unpatch();
});

const patchGetWallet = () => {
  patch(UniswapRoutes.ethereum, 'getWallet', () => {
    return {
      address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
    };
  });
};

const patchInit = () => {
    patch(UniswapRoutes.uniswap, 'init', async ()  => {
    return;
  });
};

const patchStoredTokenList = () => {
  patch(UniswapRoutes.ethereum, 'storedTokenList', () => {
    return [
      {
        chainId: 42,
        name: 'WETH',
        symbol: 'WETH',
        address: '0xd0A1E359811322d97991E03f863a0C30C2cF029C',
        decimals: 18,
      },
      {
        chainId: 42,
        name: 'DAI',
        symbol: 'DAI',
        address: '0x4f96fe3b7a6cf9725f59d353f723c1bdb64ca6aa',
        decimals: 18,
      },
    ];
  });
};

const patchGetTokenBySymbol = () => {
  patch(UniswapRoutes.ethereum, 'getTokenBySymbol', (symbol: string) => {
    if (symbol === 'WETH') {
      return {
        chainId: 42,
        name: 'WETH',
        symbol: 'WETH',
        address: '0xd0A1E359811322d97991E03f863a0C30C2cF029C',
        decimals: 18,
      };
    } else {
      return {
        chainId: 42,
        name: 'DAI',
        symbol: 'DAI',
        address: '0x4f96fe3b7a6cf9725f59d353f723c1bdb64ca6aa',
        decimals: 18,
      };
    }
  });
};

const patchGasPrice = () => {
  patch(UniswapRoutes.ethereum, 'gasPrice', () => 100);
};

const patchPriceSwapOut = () => {
  patch(UniswapRoutes.uniswap, 'priceSwapOut', () => {
    return {
      expectedAmount: {
        toSignificant: () => 100,
      },
      trade: {
        executionPrice: {
          invert: jest.fn().mockReturnValue({
            toSignificant: jest.fn().mockReturnValue(100),
          }),
        },
      },
    };
  });
};

const patchConfig = () => {
  patch(ConfigManager.config, 'UNISWAP_GAS_LIMIT', 150688);
  patch(ConfigManager.config, 'ETHEREUM_CHAIN', 'kovan');
};

const patchGetNonce = () => {
  patch(UniswapRoutes.ethereum.nonceManager, 'getNonce', () => 21);
};

const patchExecuteTrade = () => {
  patch(UniswapRoutes.uniswap, 'executeTrade', () => {
    return { nonce: 21, hash: '000000000000000' };
  });
};

describe('POST /eth/uniswap/trade', () => {
  it('should return 200', async () => {
    patchGetWallet();
    patchInit();
    patchStoredTokenList();
    patchGetTokenBySymbol();
    patchGasPrice();
    patchPriceSwapOut();
    patchConfig();
    patchGetNonce();
    patchExecuteTrade();

    await request(app)
      .post(`/eth/uniswap/trade`)
      .send({
        quote: 'DAI',
        base: 'WETH',
        amount: '10000',
        privateKey:
          'da857cbda0ba96757fed842617a40693d06d00001e55aa972955039ae747bac4',
        side: 'BUY',
        nonce: 21,
      })
      .set('Accept', 'application/json')
      .expect(200)
      .then((res: any) => {
        expect(res.body.nonce).toEqual(21);
      });
  });

    it('should return 404 when parameters are incorrect', async () => {
        patchInit();
    await request(app)
      .post(`/eth/uniswap/trade`)
      .send({
        quote: 'DAI',
        base: 'WETH',
        amount: 10000,
        privateKey: 'da8',
        side: 'comprar',
      })
      .set('Accept', 'application/json')
      .expect(404);
  });
});
