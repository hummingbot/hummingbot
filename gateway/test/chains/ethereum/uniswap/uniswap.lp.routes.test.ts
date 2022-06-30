import express from 'express';
import { Express } from 'express-serve-static-core';
import request from 'supertest';
import { Ethereum } from '../../../../src/chains/ethereum/ethereum';
import { UniswapLP } from '../../../../src/connectors/uniswap/uniswap.lp';
import { AmmLiquidityRoutes } from '../../../../src/amm/amm.routes';
import { patch, unpatch } from '../../../services/patch';
import { patchEVMNonceManager } from '../../../evm.nonce.mock';

let app: Express;
let ethereum: Ethereum;
let uniswap: UniswapLP;

beforeAll(async () => {
  app = express();
  app.use(express.json());
  ethereum = Ethereum.getInstance('kovan');
  patchEVMNonceManager(ethereum.nonceManager);
  await ethereum.init();

  uniswap = UniswapLP.getInstance('ethereum', 'kovan');
  await uniswap.init();
  app.use('/amm/liquidity', AmmLiquidityRoutes.router);
});

beforeEach(() => {
  patchEVMNonceManager(ethereum.nonceManager);
});

afterEach(() => {
  unpatch();
});

afterAll(async () => {
  await ethereum.close();
});

const address: string = '0xFaA12FD102FE8623C9299c72B03E45107F2772B5';

const patchGetWallet = () => {
  patch(ethereum, 'getWallet', () => {
    return {
      address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
    };
  });
};

const patchInit = () => {
  patch(uniswap, 'init', async () => {
    return;
  });
};

const patchStoredTokenList = () => {
  patch(ethereum, 'tokenList', () => {
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
  patch(ethereum, 'getTokenBySymbol', (symbol: string) => {
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

const patchGetTokenByAddress = () => {
  patch(uniswap, 'getTokenByAddress', () => {
    return {
      chainId: 42,
      name: 'WETH',
      symbol: 'WETH',
      address: '0xd0A1E359811322d97991E03f863a0C30C2cF029C',
      decimals: 18,
    };
  });
};

const patchGasPrice = () => {
  patch(ethereum, 'gasPrice', () => 100);
};

const patchGetNonce = () => {
  patch(ethereum.nonceManager, 'getNonce', () => 21);
};

const patchAddPosition = () => {
  patch(uniswap, 'addPosition', () => {
    return { nonce: 21, hash: '000000000000000' };
  });
};

const patchRemovePosition = () => {
  patch(uniswap, 'reducePosition', () => {
    return { nonce: 21, hash: '000000000000000' };
  });
};

const patchCollectFees = () => {
  patch(uniswap, 'collectFees', () => {
    return { nonce: 21, hash: '000000000000000' };
  });
};

const patchPosition = () => {
  patch(uniswap, 'getPosition', () => {
    return {
      token0: 'DAI',
      token1: 'WETH',
      fee: 300,
      lowerPrice: '1',
      upperPrice: '5',
      amount0: '1',
      amount1: '1',
      unclaimedToken0: '1',
      unclaimedToken1: '1',
    };
  });
};

describe('POST /liquidity/add', () => {
  it('should return 200 when all parameter are OK', async () => {
    patchGetWallet();
    patchInit();
    patchStoredTokenList();
    patchGetTokenBySymbol();
    patchGetTokenByAddress();
    patchGasPrice();
    patchAddPosition();
    patchGetNonce();

    await request(app)
      .post(`/amm/liquidity/add`)
      .send({
        address: address,
        token0: 'DAI',
        token1: 'WETH',
        amount0: '1',
        amount1: '1',
        fee: 'LOW',
        lowerPrice: '1',
        upperPrice: '5',
        chain: 'ethereum',
        network: 'kovan',
        connector: 'uniswapLP',
      })
      .set('Accept', 'application/json')
      .expect(200);
  });

  it('should return 500 for unrecognized token0 symbol', async () => {
    patchGetWallet();
    patchInit();
    patchStoredTokenList();
    patchGetTokenBySymbol();

    await request(app)
      .post(`/amm/liquidity/add`)
      .send({
        address: address,
        token0: 'DOGE',
        token1: 'WETH',
        amount0: '1',
        amount1: '1',
        fee: 'LOW',
        lowerPrice: '1',
        upperPrice: '5',
        chain: 'ethereum',
        network: 'kovan',
        connector: 'uniswapLP',
      })
      .set('Accept', 'application/json')
      .expect(500);
  });

  it('should return 404 for invalid fee tier', async () => {
    patchGetWallet();
    patchInit();
    patchStoredTokenList();
    patchGetTokenBySymbol();
    patchGetTokenByAddress();

    await request(app)
      .post(`/amm/liquidity/add`)
      .send({
        address: address,
        token0: 'DAI',
        token1: 'WETH',
        amount0: '1',
        amount1: '1',
        fee: 300,
        lowerPrice: '1',
        upperPrice: '5',
        chain: 'ethereum',
        network: 'kovan',
        connector: 'uniswapLP',
      })
      .set('Accept', 'application/json')
      .expect(404);
  });

  it('should return 500 when the helper operation fails', async () => {
    patchGetWallet();
    patchInit();
    patchStoredTokenList();
    patchGetTokenBySymbol();
    patchGetTokenByAddress();
    patch(uniswap, 'addPositionHelper', () => {
      return 'error';
    });

    await request(app)
      .post(`/amm/liquidity/add`)
      .send({
        address: address,
        token0: 'DAI',
        token1: 'WETH',
        amount0: '1',
        amount1: '1',
        fee: 'LOW',
        lowerPrice: '1',
        upperPrice: '5',
        chain: 'ethereum',
        network: 'kovan',
        connector: 'uniswapLP',
      })
      .set('Accept', 'application/json')
      .expect(500);
  });
});

describe('POST /liquidity/remove', () => {
  const patchForBuy = () => {
    patchGetWallet();
    patchInit();
    patchStoredTokenList();
    patchGetTokenBySymbol();
    patchGetTokenByAddress();
    patchGasPrice();
    patchRemovePosition();
    patchGetNonce();
  };
  it('should return 200 when all parameter are OK', async () => {
    patchForBuy();
    await request(app)
      .post(`/amm/liquidity/remove`)
      .send({
        address: address,
        tokenId: 2732,
        chain: 'ethereum',
        network: 'kovan',
        connector: 'uniswapLP',
      })
      .set('Accept', 'application/json')
      .expect(200);
  });

  it('should return 404 when the tokenId is invalid', async () => {
    patchGetWallet();
    patchInit();
    patchStoredTokenList();
    patchGetTokenBySymbol();
    patchGetTokenByAddress();

    await request(app)
      .post(`/amm/liquidity/remove`)
      .send({
        address: address,
        tokenId: 'Invalid',
        chain: 'ethereum',
        network: 'kovan',
        connector: 'uniswapLP',
      })
      .set('Accept', 'application/json')
      .expect(404);
  });
});

describe('POST /liquidity/collect_fees', () => {
  const patchForBuy = () => {
    patchGetWallet();
    patchInit();
    patchGasPrice();
    patchCollectFees();
    patchGetNonce();
  };
  it('should return 200 when all parameter are OK', async () => {
    patchForBuy();
    await request(app)
      .post(`/amm/liquidity/collect_fees`)
      .send({
        address: address,
        tokenId: 2732,
        chain: 'ethereum',
        network: 'kovan',
        connector: 'uniswapLP',
      })
      .set('Accept', 'application/json')
      .expect(200);
  });

  it('should return 404 when the tokenId is invalid', async () => {
    patchGetWallet();
    patchInit();
    patchStoredTokenList();
    patchGetTokenBySymbol();
    patchGetTokenByAddress();

    await request(app)
      .post(`/amm/liquidity/collect_fees`)
      .send({
        address: address,
        tokenId: 'Invalid',
        chain: 'ethereum',
        network: 'kovan',
        connector: 'uniswapLP',
      })
      .set('Accept', 'application/json')
      .expect(404);
  });
});

describe('POST /liquidity/position', () => {
  it('should return 200 when all parameter are OK', async () => {
    patchInit();
    patchStoredTokenList();
    patchGetTokenBySymbol();
    patchGetTokenByAddress();
    patchPosition();

    await request(app)
      .post(`/amm/liquidity/position`)
      .send({
        tokenId: 2732,
        chain: 'ethereum',
        network: 'kovan',
        connector: 'uniswapLP',
      })
      .set('Accept', 'application/json')
      .expect(200);
  });

  it('should return 404 when the tokenId is invalid', async () => {
    patchInit();
    patchStoredTokenList();
    patchGetTokenBySymbol();
    patchGetTokenByAddress();

    await request(app)
      .post(`/amm/liquidity/position`)
      .send({
        tokenId: 'Invalid',
        chain: 'ethereum',
        network: 'kovan',
        connector: 'uniswapLP',
      })
      .set('Accept', 'application/json')
      .expect(404);
  });
});

describe('POST /liquidity/price', () => {
  const patchForBuy = () => {
    patchInit();
    patchStoredTokenList();
    patchGetTokenBySymbol();
    patchGetTokenByAddress();
    patch(uniswap, 'poolPrice', () => {
      return ['100', '105'];
    });
  };
  it('should return 200 when all parameter are OK', async () => {
    patchForBuy();
    await request(app)
      .post(`/amm/liquidity/price`)
      .send({
        token0: 'DAI',
        token1: 'WETH',
        fee: 'LOW',
        period: 120,
        interval: 60,
        chain: 'ethereum',
        network: 'kovan',
        connector: 'uniswapLP',
      })
      .set('Accept', 'application/json')
      .expect(200);
  });

  it('should return 404 when the fee is invalid', async () => {
    patchGetWallet();
    patchInit();
    patchStoredTokenList();
    patchGetTokenBySymbol();
    patchGetTokenByAddress();

    await request(app)
      .post(`/amm/liquidity/price`)
      .send({
        token0: 'DAI',
        token1: 'WETH',
        fee: 11,
        period: 120,
        interval: 60,
        chain: 'ethereum',
        network: 'kovan',
        connector: 'uniswapLP',
      })
      .set('Accept', 'application/json')
      .expect(404);
  });
});
