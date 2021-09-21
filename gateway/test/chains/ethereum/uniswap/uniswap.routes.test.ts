import express from 'express';
import { Express } from 'express-serve-static-core';
import request from 'supertest';
import { UniswapRoutes } from '../../../../src/chains/ethereum/uniswap/uniswap.routes';
import { ConfigManager } from '../../../../src/services/config-manager';

let app: Express;

beforeAll(async () => {
  app = express();
  app.use(express.json());
  app.use('/eth/uniswap', UniswapRoutes.router);
});

describe('POST /eth/uniswap/trade', () => {
  it('should return 200', async () => {
    // getWallet (network call)
    UniswapRoutes.ethereum.getWallet = jest.fn().mockReturnValue({
      address: '0x0000000000000000000',
    });

    // init (network call)
    UniswapRoutes.uniswap.init = jest.fn().mockReturnValue(() => {
      return;
    });

    // storedTokenList (network call)
    jest
      .spyOn(UniswapRoutes.ethereum, 'storedTokenList', 'get')
      .mockReturnValue([
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
      ]);

    // getTokenBySymbol (network call or read file)
    UniswapRoutes.ethereum.getTokenBySymbol = jest
      .fn()
      .mockReturnValue((symbol: string) => {
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

    // priceSwapOut (network call)
    UniswapRoutes.uniswap.priceSwapOut = jest.fn().mockReturnValue({
      expectedAmount: { toSignificant: () => 100 },
      trade: {
        executionPrice: {
          invert: jest.fn().mockReturnValue({
            toSignificant: jest.fn().mockReturnValue(100),
          }),
        },
      },
    });

    // gasPrice (network call)
    jest.spyOn(UniswapRoutes.ethereum, 'gasPrice', 'get').mockReturnValue(100);

    // config (read config file)
    ConfigManager.config.UNISWAP_GAS_LIMIT = 150688;
    ConfigManager.config.ETHEREUM_CHAIN = 'kovan';

    // getNonce (network call)
    UniswapRoutes.ethereum.nonceManager.getNonce = jest
      .fn()
      .mockReturnValue(21);

    // executeTrade (network call)
    UniswapRoutes.uniswap.executeTrade = jest
      .fn()
      .mockReturnValue({ nonce: 21, hash: '000000000000000' });

    await request(app)
      .post(`/eth/uniswap/trade`)
      .send({
        quote: 'DAI',
        base: 'WETH',
        amount: '10000',
        privateKey: 'abc123',
        side: 'BUY',
        nonce: 21,
      })
      .set('Accept', 'application/json')
      .expect(200)
      .then((res: any) => {
        expect(res.body.nonce).toEqual(21);
      });
  });
});
