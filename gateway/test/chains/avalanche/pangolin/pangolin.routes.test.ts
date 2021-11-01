import express from 'express';
import { Express } from 'express-serve-static-core';
import request from 'supertest';
import { PangolinRoutes } from '../../../../src/chains/avalanche/pangolin/pangolin.routes';
import { ConfigManager } from '../../../../src/services/config-manager';
import { patch, unpatch } from '../../../services/patch';

let app: Express;

beforeAll(async () => {
  app = express();
  app.use(express.json());
  app.use('/avalanche/pangolin', PangolinRoutes.router);
});

afterEach(unpatch);

const patchGetWallet = () => {
  patch(PangolinRoutes.avalanche, 'getWallet', () => {
    return {
      address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
    };
  });
};

const patchInit = () => {
  patch(PangolinRoutes.avalanche, 'init', async () => {
    return;
  });
};

const patchStoredTokenList = () => {
  patch(PangolinRoutes.avalanche, 'storedTokenList', () => {
    return [
      {
        chainId: 43114,
        address: '0x60781C2586D68229fde47564546784ab3fACA982',
        decimals: 18,
        name: 'Pangolin',
        symbol: 'PNG',
        logoURI:
          'https://raw.githubusercontent.com/ava-labs/bridge-tokens/main/avalanche-tokens/0x60781C2586D68229fde47564546784ab3fACA982/logo.png',
      },
      {
        chainId: 43114,
        address: '0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7',
        decimals: 18,
        name: 'Wrapped AVAX',
        symbol: 'WAVAX',
        logoURI:
          'https://raw.githubusercontent.com/ava-labs/bridge-tokens/main/avalanche-tokens/0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7/logo.png',
      },
    ];
  });
};

const patchGetTokenBySymbol = () => {
  patch(PangolinRoutes.avalanche, 'getTokenBySymbol', (symbol: string) => {
    if (symbol === 'WETH') {
      return {
        chainId: 43114,
        address: '0x60781C2586D68229fde47564546784ab3fACA982',
        decimals: 18,
        name: 'Pangolin',
        symbol: 'PNG',
        logoURI:
          'https://raw.githubusercontent.com/ava-labs/bridge-tokens/main/avalanche-tokens/0x60781C2586D68229fde47564546784ab3fACA982/logo.png',
      };
    } else {
      return {
        chainId: 43114,
        address: '0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7',
        decimals: 18,
        name: 'Wrapped AVAX',
        symbol: 'WAVAX',
        logoURI:
          'https://raw.githubusercontent.com/ava-labs/bridge-tokens/main/avalanche-tokens/0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7/logo.png',
      };
    }
  });
};

const patchGasPrice = () => {
  patch(PangolinRoutes.avalanche, 'gasPrice', () => 100);
};

const patchPriceSwapOut = () => {
  patch(PangolinRoutes.avalanche, 'priceSwapOut', () => {
    return {
      expectedAmount: {
        toSignificant: () => 100,
      },
      trade: {
        executionPrice: {
          invert: jest.fn().mockReturnValue({
            toSignificant: () => 100,
          }),
        },
      },
    };
  });
};

const patchConfig = () => {
  patch(ConfigManager.config, 'PANGOLIN_GAS_LIMIT', 150688);
  patch(ConfigManager.config, 'AVALANCHE_CHAIN', 'fuji');
};

const patchGetNonce = () => {
  patch(PangolinRoutes.avalanche.nonceManager, 'getNonce', () => 21);
};

const patchExecuteTrade = () => {
  patch(PangolinRoutes.avalanche, 'executeTrade', () => {
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
        quote: 'PNG',
        base: 'DAI.e',
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
        quote: 'PNG',
        base: 'DAI.e',
        amount: 10000,
        privateKey: 'da8',
        side: 'comprar',
      })
      .set('Accept', 'application/json')
      .expect(404);
  });
});
