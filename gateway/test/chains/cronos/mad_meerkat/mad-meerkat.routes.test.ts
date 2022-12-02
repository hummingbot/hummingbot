import request from 'supertest';
import { patch, unpatch } from '../../../services/patch';
import { gatewayApp } from '../../../../src/app';
import { Cronos } from '../../../../src/chains/cronos/cronos';
import { MadMeerkat } from '../../../../src/connectors/mad_meerkat/mad_meerkat';
import { patchEVMNonceManager } from '../../../evm.nonce.mock';
let cronos: Cronos;
let madMeerkat: MadMeerkat;

beforeAll(async () => {
  cronos = Cronos.getInstance('mainnet');
  patchEVMNonceManager(cronos.nonceManager);
  await cronos.init();
  madMeerkat = MadMeerkat.getInstance('cronos', 'mainnet') as MadMeerkat;
  await madMeerkat.init();
});

beforeEach(() => {
  patchEVMNonceManager(cronos.nonceManager);
});

afterEach(() => {
  unpatch();
});

afterAll(async () => {
  await cronos.close();
});

const address: string = '0xFaA12FD102FE8623C9299c72B03E45107F2772B5';

const patchGetWallet = () => {
  patch(cronos, 'getWallet', () => {
    return {
      address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
    };
  });
};

const patchStoredTokenList = () => {
  patch(cronos, 'tokenList', () => {
    return [
      {
        chainId: 43114,
        name: 'WETH',
        symbol: 'WETH',
        address: '0xd0A1E359811322d97991E03f863a0C30C2cF029C',
        decimals: 18,
      },
      {
        chainId: 43114,
        name: 'Wrapped AVAX',
        symbol: 'WAVAX',
        address: '0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7',
        decimals: 18,
      },
    ];
  });
};

const patchGetTokenBySymbol = () => {
  patch(cronos, 'getTokenBySymbol', (symbol: string) => {
    if (symbol === 'WETH') {
      return {
        chainId: 43114,
        name: 'WETH',
        symbol: 'WETH',
        address: '0xd0A1E359811322d97991E03f863a0C30C2cF029C',
        decimals: 18,
      };
    } else {
      return {
        chainId: 42,
        name: 'WAVAX',
        symbol: 'WAVAX',
        address: '0x4f96fe3b7a6cf9725f59d353f723c1bdb64ca6aa',
        decimals: 18,
      };
    }
  });
};

const patchGetTokenByAddress = () => {
  patch(madMeerkat, 'getTokenByAddress', () => {
    return {
      chainId: 43114,
      name: 'WETH',
      symbol: 'WETH',
      address: '0xd0A1E359811322d97991E03f863a0C30C2cF029C',
      decimals: 18,
    };
  });
};

const patchGasPrice = () => {
  patch(cronos, 'gasPrice', () => 100);
};

const patchEstimateBuyTrade = () => {
  patch(madMeerkat, 'estimateBuyTrade', () => {
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
  patch(madMeerkat, 'estimateSellTrade', () => {
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
  patch(cronos.nonceManager, 'getNonce', () => 21);
};

const patchExecuteTrade = () => {
  patch(madMeerkat, 'executeTrade', () => {
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
        chain: 'cronos',
        network: 'mainnet',
        connector: 'mad_meerkat',
        quote: 'WAVAX',
        base: 'WETH',
        amount: '10000',
        side: 'BUY',
      })
      .set('Accept', 'application/json')
      .expect(200)
      .then((res: any) => {
        expect(res.body.amount).toEqual('10000.000000000000000000');
        expect(res.body.rawAmount).toEqual('10000000000000000000000');
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
        chain: 'cronos',
        network: 'mainnet',
        connector: 'mad_meerkat',
        quote: 'WAVAX',
        base: 'WETH',
        amount: '10000',
        side: 'SELL',
      })
      .set('Accept', 'application/json')
      .expect(200)
      .then((res: any) => {
        expect(res.body.amount).toEqual('10000.000000000000000000');
        expect(res.body.rawAmount).toEqual('10000000000000000000000');
      });
  });

  it('should return 500 for unrecognized quote symbol', async () => {
    patchGetWallet();
    patchStoredTokenList();
    patch(cronos, 'getTokenBySymbol', (symbol: string) => {
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
        chain: 'cronos',
        network: 'mainnet',
        connector: 'mad_meerkat',
        quote: 'DOGE',
        base: 'WETH',
        amount: '10000',
        side: 'SELL',
      })
      .set('Accept', 'application/json')
      .expect(500);
  });

  it('should return 500 for unrecognized base symbol', async () => {
    patchGetWallet();
    patchStoredTokenList();
    patch(cronos, 'getTokenBySymbol', (symbol: string) => {
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
        chain: 'cronos',
        network: 'mainnet',
        connector: 'mad_meerkat',
        quote: 'WAVAX',
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
    patchGetNonce();
    patchExecuteTrade();
  };
  it('should return 200 for BUY', async () => {
    patchForBuy();
    await request(gatewayApp)
      .post(`/amm/trade`)
      .send({
        chain: 'cronos',
        network: 'mainnet',
        connector: 'mad_meerkat',
        quote: 'WAVAX',
        base: 'WETH',
        amount: '10000',
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
    await request(gatewayApp)
      .post(`/amm/trade`)
      .send({
        chain: 'cronos',
        network: 'mainnet',
        connector: 'mad_meerkat',
        quote: 'WAVAX',
        base: 'WETH',
        amount: '10000',
        address,
        side: 'BUY',
      })
      .set('Accept', 'application/json')
      .expect(200);
  });

  it('should return 200 for BUY with maxFeePerGas and maxPriorityFeePerGas', async () => {
    patchForBuy();
    await request(gatewayApp)
      .post(`/amm/trade`)
      .send({
        chain: 'cronos',
        network: 'mainnet',
        connector: 'mad_meerkat',
        quote: 'WAVAX',
        base: 'WETH',
        amount: '10000',
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
    await request(gatewayApp)
      .post(`/amm/trade`)
      .send({
        chain: 'cronos',
        network: 'mainnet',
        connector: 'mad_meerkat',
        quote: 'WAVAX',
        base: 'WETH',
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
    await request(gatewayApp)
      .post(`/amm/trade`)
      .send({
        chain: 'cronos',
        network: 'mainnet',
        connector: 'mad_meerkat',
        quote: 'WAVAX',
        base: 'WETH',
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
    await request(gatewayApp)
      .post(`/amm/trade`)
      .send({
        chain: 'cronos',
        network: 'mainnet',
        connector: 'mad_meerkat',
        quote: 'WAVAX',
        base: 'WETH',
        amount: 10000,
        address: 'da8',
        side: 'comprar',
      })
      .set('Accept', 'application/json')
      .expect(404);
  });

  it('should return 500 when base token is unknown', async () => {
    patchForSell();
    patch(cronos, 'getTokenBySymbol', (symbol: string) => {
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

    await request(gatewayApp)
      .post(`/amm/trade`)
      .send({
        chain: 'cronos',
        network: 'mainnet',
        connector: 'mad_meerkat',
        quote: 'WETH',
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
    patch(cronos, 'getTokenBySymbol', (symbol: string) => {
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

    await request(gatewayApp)
      .post(`/amm/trade`)
      .send({
        chain: 'cronos',
        network: 'mainnet',
        connector: 'mad_meerkat',
        quote: 'BITCOIN',
        base: 'WETH',
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
    await request(gatewayApp)
      .post(`/amm/trade`)
      .send({
        chain: 'cronos',
        network: 'mainnet',
        connector: 'mad_meerkat',
        quote: 'WAVAX',
        base: 'WETH',
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
    await request(gatewayApp)
      .post(`/amm/trade`)
      .send({
        chain: 'cronos',
        network: 'mainnet',
        connector: 'mad_meerkat',
        quote: 'WAVAX',
        base: 'WETH',
        amount: '10000',
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
    await request(gatewayApp)
      .post(`/amm/trade`)
      .send({
        chain: 'cronos',
        network: 'mainnet',
        connector: 'mad_meerkat',
        quote: 'WAVAX',
        base: 'WETH',
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
    await request(gatewayApp)
      .post(`/amm/trade`)
      .send({
        chain: 'cronos',
        network: 'mainnet',
        connector: 'mad_meerkat',
        quote: 'WAVAX',
        base: 'WETH',
        amount: '10000',
        address,
        side: 'BUY',
        nonce: 21,
        limitPrice: '9',
      })
      .set('Accept', 'application/json')
      .expect(500);
  });
});
