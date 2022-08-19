import request from 'supertest';
import { gatewayApp } from '../../../../src/app';
import { BinanceSmartChain } from '../../../../src/chains/binance-smart-chain/binance-smart-chain';
import { PancakeSwap } from '../../../../src/connectors/pancakeswap/pancakeswap';
import { patch, unpatch } from '../../../services/patch';
import { patchEVMNonceManager } from '../../../evm.nonce.mock';

let bsc: BinanceSmartChain;
let pancakeswap: PancakeSwap;

beforeAll(async () => {
  bsc = BinanceSmartChain.getInstance('testnet');
  patchEVMNonceManager(bsc.nonceManager);
  await bsc.init();
  pancakeswap = PancakeSwap.getInstance('binance-smart-chain', 'testnet');
  await pancakeswap.init();
});

beforeEach(() => {
  patchEVMNonceManager(bsc.nonceManager);
});

afterEach(() => {
  unpatch();
});

afterAll(async () => {
  await bsc.close();
});

const address: string = '0x242532ebDfcc760f2Ddfe8378eB51f5F847CE5bD';

const patchGetWallet = () => {
  patch(bsc, 'getWallet', () => {
    return {
      address: address,
    };
  });
};

const patchStoredTokenList = () => {
  patch(bsc, 'tokenList', () => {
    return [
      {
        chainId: 97,
        name: 'WBNB',
        symbol: 'WBNB',
        address: '0xae13d989dac2f0debff460ac112a837c89baa7cd',
        decimals: 18,
      },
      {
        chainId: 97,
        name: 'DAI',
        symbol: 'DAI',
        address: '0x8a9424745056Eb399FD19a0EC26A14316684e274',
        decimals: 18,
      },
    ];
  });
};

const patchGetTokenBySymbol = () => {
  patch(bsc, 'getTokenBySymbol', (symbol: string) => {
    if (symbol === 'WBNB') {
      return {
        chainId: 97,
        name: 'WBNB',
        symbol: 'WBNB',
        address: '0xae13d989dac2f0debff460ac112a837c89baa7cd',
        decimals: 18,
      };
    } else {
      return {
        chainId: 97,
        name: 'DAI',
        symbol: 'DAI',
        address: '0x8a9424745056Eb399FD19a0EC26A14316684e274',
        decimals: 18,
      };
    }
  });
};

const patchGetTokenByAddress = () => {
  patch(pancakeswap, 'getTokenByAddress', () => {
    return {
      chainId: 97,
      name: 'WBNB',
      symbol: 'WBNB',
      address: '0xae13d989dac2f0debff460ac112a837c89baa7cd',
      decimals: 18,
    };
  });
};

const patchGasPrice = () => {
  patch(bsc, 'gasPrice', () => 100);
};

const patchEstimateBuyTrade = () => {
  patch(pancakeswap, 'estimateBuyTrade', () => {
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
  patch(pancakeswap, 'estimateSellTrade', () => {
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
  patch(bsc.nonceManager, 'getNonce', () => 21);
};

const patchExecuteTrade = () => {
  patch(pancakeswap, 'executeTrade', () => {
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
        chain: 'binance-smart-chain',
        network: 'testnet',
        connector: 'pancakeswap',
        quote: 'DAI',
        base: 'WBNB',
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
        chain: 'binance-smart-chain',
        network: 'testnet',
        connector: 'pancakeswap',
        quote: 'DAI',
        base: 'WBNB',
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
    patch(bsc, 'getTokenBySymbol', (symbol: string) => {
      if (symbol === 'WBNB') {
        return {
          chainId: 97,
          name: 'WBNB',
          symbol: 'WBNB',
          address: '0xae13d989dac2f0debff460ac112a837c89baa7cd',
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
        chain: 'binance-smart-chain',
        network: 'testnet',
        connector: 'pancakeswap',
        quote: 'DOGE',
        base: 'WBNB',
        amount: '10000',
        side: 'SELL',
      })
      .set('Accept', 'application/json')
      .expect(500);
  });

  it('should return 500 for unrecognized base symbol', async () => {
    patchGetWallet();
    patchStoredTokenList();
    patch(bsc, 'getTokenBySymbol', (symbol: string) => {
      if (symbol === 'WBNB') {
        return {
          chainId: 97,
          name: 'WBNB',
          symbol: 'WBNB',
          address: '0xae13d989dac2f0debff460ac112a837c89baa7cd',
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
        chain: 'binance-smart-chain',
        network: 'testnet',
        connector: 'pancakeswap',
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
    patchGetNonce();
    patchExecuteTrade();
  };
  it('should return 200 for BUY', async () => {
    patchForBuy();
    await request(gatewayApp)
      .post(`/amm/trade`)
      .send({
        chain: 'binance-smart-chain',
        network: 'testnet',
        connector: 'pancakeswap',
        quote: 'DAI',
        base: 'WBNB',
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
        chain: 'binance-smart-chain',
        network: 'testnet',
        connector: 'pancakeswap',
        quote: 'DAI',
        base: 'WBNB',
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
        chain: 'binance-smart-chain',
        network: 'testnet',
        connector: 'pancakeswap',
        quote: 'DAI',
        base: 'WBNB',
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
        chain: 'binance-smart-chain',
        network: 'testnet',
        connector: 'pancakeswap',
        quote: 'DAI',
        base: 'WBNB',
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
        chain: 'binance-smart-chain',
        network: 'testnet',
        connector: 'pancakeswap',
        quote: 'DAI',
        base: 'WBNB',
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
        chain: 'binance-smart-chain',
        network: 'testnet',
        connector: 'pancakeswap',
        quote: 'DAI',
        base: 'WBNB',
        amount: 10000,
        address: 'da8',
        side: 'comprar',
      })
      .set('Accept', 'application/json')
      .expect(404);
  });

  it('should return 500 when base token is unknown', async () => {
    patchForSell();
    patch(bsc, 'getTokenBySymbol', (symbol: string) => {
      if (symbol === 'WBNB') {
        return {
          chainId: 97,
          name: 'WBNB',
          symbol: 'WBNB',
          address: '0xae13d989dac2f0debff460ac112a837c89baa7cd',
          decimals: 18,
        };
      } else {
        return null;
      }
    });

    await request(gatewayApp)
      .post(`/amm/trade`)
      .send({
        chain: 'binance-smart-chain',
        network: 'testnet',
        connector: 'pancakeswap',
        quote: 'WBNB',
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
    patch(bsc, 'getTokenBySymbol', (symbol: string) => {
      if (symbol === 'WBNB') {
        return {
          chainId: 97,
          name: 'WBNB',
          symbol: 'WBNB',
          address: '0xae13d989dac2f0debff460ac112a837c89baa7cd',
          decimals: 18,
        };
      } else {
        return null;
      }
    });

    await request(gatewayApp)
      .post(`/amm/trade`)
      .send({
        chain: 'binance-smart-chain',
        network: 'testnet',
        connector: 'pancakeswap',
        quote: 'BITCOIN',
        base: 'WBNB',
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
        chain: 'binance-smart-chain',
        network: 'testnet',
        connector: 'pancakeswap',
        quote: 'DAI',
        base: 'WBNB',
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
        chain: 'binance-smart-chain',
        network: 'testnet',
        connector: 'pancakeswap',
        quote: 'DAI',
        base: 'WBNB',
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
        chain: 'binance-smart-chain',
        network: 'testnet',
        connector: 'pancakeswap',
        quote: 'DAI',
        base: 'WBNB',
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
        chain: 'binance-smart-chain',
        network: 'testnet',
        connector: 'pancakeswap',
        quote: 'DAI',
        base: 'WBNB',
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
