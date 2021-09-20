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
    UniswapRoutes.ethereum.getWallet = jest.fn().mockReturnValue(() => {
      address: '0x0000000000000000000';
    });

    // prevent some network calls
    UniswapRoutes.uniswap.init = jest.fn().mockReturnValue(() => {
      return;
    });

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

    jest.spyOn(UniswapRoutes.ethereum, 'gasPrice', 'get').mockReturnValue(100);

    ConfigManager.config.UNISWAP_GAS_LIMIT = 150688;
    ConfigManager.config.ETHEREUM_CHAIN = 'kovan';
    UniswapRoutes.ethereum.nonceManager.getNonce = jest
      .fn()
      .mockReturnValue(() => Promise.resolve(2));
    UniswapRoutes.ethereum.approveERC20 = jest.fn().mockReturnValue(() => {
      chainId: 42;
      name: 'WETH';
      symbol: 'WETH';
      address: '0xd0A1E359811322d97991E03f863a0C30C2cF029C';
      decimals: 18;
    });

    UniswapRoutes.uniswap.executeTrade = jest
      .fn()
      .mockReturnValue({ nonce: 1, hash: '000000000000000' });

    const res = await request(app)
      .post(`/eth/uniswap/trade`)
      .send({
        quote: 'DAI',
        base: 'WETH',
        amount: '10000',
        privateKey: 'abc123',
        side: 'BUY',
        nonce: 21,
      })
      .set('Accept', 'application/json');
    expect(res.statusCode).toEqual(200);
  });
});
