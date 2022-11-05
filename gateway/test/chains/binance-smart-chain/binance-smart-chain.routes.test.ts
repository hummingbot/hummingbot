import request from 'supertest';
import { patch, unpatch } from '../../services/patch';
import { gatewayApp } from '../../../src/app';
import {
  NETWORK_ERROR_CODE,
  NETWORK_ERROR_MESSAGE,
  OUT_OF_GAS_ERROR_CODE,
  OUT_OF_GAS_ERROR_MESSAGE,
  UNKNOWN_ERROR_ERROR_CODE,
  UNKNOWN_ERROR_MESSAGE,
} from '../../../src/services/error-handler';
import * as transactionSuccesful from '../ethereum/fixtures/transaction-succesful.json';
import * as transactionSuccesfulReceipt from '../ethereum//fixtures/transaction-succesful-receipt.json';
import * as transactionOutOfGas from '../ethereum//fixtures/transaction-out-of-gas.json';
import * as transactionOutOfGasReceipt from '../ethereum/fixtures/transaction-out-of-gas-receipt.json';
import { BinanceSmartChain } from '../../../src/chains/binance-smart-chain/binance-smart-chain';
import { patchEVMNonceManager } from '../../evm.nonce.mock';

let bsc: BinanceSmartChain;

beforeAll(async () => {
  bsc = BinanceSmartChain.getInstance('testnet');

  patchEVMNonceManager(bsc.nonceManager);

  await bsc.init();
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
      address,
    };
  });
};

const patchGetNonce = () => {
  patch(bsc.nonceManager, 'getNonce', () => 0);
};

const patchGetTokenBySymbol = () => {
  patch(bsc, 'getTokenBySymbol', () => {
    return {
      chainId: 97,
      address: '0xae13d989dac2f0debff460ac112a837c89baa7cd',
      decimals: 18,
      name: 'WBNB Token',
      symbol: 'WBNB',
      logoURI:
        'https://exchange.pancakeswap.finance/images/coins/0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c.png',
    };
  });
};

const patchApproveERC20 = () => {
  patch(bsc, 'approveERC20', () => {
    return {
      type: 2,
      chainId: 97,
      nonce: 0,
      maxPriorityFeePerGas: { toString: () => '106000000000' },
      maxFeePerGas: { toString: () => '106000000000' },
      gasPrice: { toString: () => null },
      gasLimit: { toString: () => '66763' },
      to: '0x8babbb98678facc7342735486c851abd7a0d17ca',
      value: { toString: () => '0' },
      data: '0x095ea7b30000000000000000000000007a250d5630b4cf539739df2c5dacb4c659f2488dffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff', // noqa: mock
      accessList: [],
      hash: '0xffdb7b393b46d3795b82c94b8d836ad6b3087a914244634fa89c3abbbf00ed72', // noqa: mock
      v: 229,
      r: '0x8800b16cbc6d468acad057dd5f724944d6aa48543cd90472e28dd5c6e90268b1', // noqa: mock
      s: '0x662ed86bb86fb40911738ab67785f6e6c76f1c989d977ca23c504ef7a4796d08', // noqa: mock
      from: '0x242532ebdfcc760f2ddfe8378eb51f5f847ce5bd',
      confirmations: 98,
    };
  });
};

const patchGetERC20Allowance = () => {
  patch(bsc, 'getERC20Allowance', () => ({ value: 1, decimals: 3 }));
};

const patchGetNativeBalance = () => {
  patch(bsc, 'getNativeBalance', () => ({ value: 1, decimals: 3 }));
};

const patchGetERC20Balance = () => {
  patch(bsc, 'getERC20Balance', () => ({ value: 1, decimals: 3 }));
};

describe('POST /evm/approve', () => {
  it('should return 200', async () => {
    patchGetWallet();
    bsc.getContract = jest.fn().mockReturnValue({
      address,
    });
    patchGetNonce();
    patchGetTokenBySymbol();
    patchApproveERC20();

    await request(gatewayApp)
      .post(`/evm/approve`)
      .send({
        chain: 'binance-smart-chain',
        network: 'testnet',
        address,
        spender: address,
        token: 'BNB',
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200)
      .then((res: any) => {
        expect(res.body.nonce).toEqual(0);
      });
  });

  it('should return 404 when parameters are invalid', async () => {
    await request(gatewayApp)
      .post(`/evm/approve`)
      .send({
        chain: 'binance-smart-chain',
        network: 'testnet',
        address,
        spender: address,
        token: 123,
        nonce: '23',
      })
      .expect(404);
  });
});

describe('POST /evm/nonce', () => {
  it('should return 200', async () => {
    patchGetWallet();
    patchGetNonce();

    await request(gatewayApp)
      .post(`/evm/nonce`)
      .send({
        chain: 'binance-smart-chain',
        network: 'testnet',
        address,
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.nonce).toBe(0));
  });
});

describe('POST /evm/allowances', () => {
  it('should return 200 asking for allowances', async () => {
    patchGetWallet();
    patchGetTokenBySymbol();
    const spender = '0x242532ebDfcc760f2Ddfe8378eB51f5F847CE5bD';
    bsc.getSpender = jest.fn().mockReturnValue(spender);
    bsc.getContract = jest.fn().mockReturnValue({
      address: '0x242532ebDfcc760f2Ddfe8378eB51f5F847CE5bD',
    });
    patchGetERC20Allowance();

    await request(gatewayApp)
      .post(`/evm/allowances`)
      .send({
        chain: 'binance-smart-chain',
        network: 'testnet',
        address: '0x242532ebDfcc760f2Ddfe8378eB51f5F847CE5bD',
        spender: spender,
        tokenSymbols: ['BNB', 'DAI'],
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.spender).toEqual(spender))
      .expect((res) => expect(res.body.approvals.BNB).toEqual('0.001'))
      .expect((res) => expect(res.body.approvals.DAI).toEqual('0.001'));
  });
});

describe('POST /network/balances', () => {
  it('should return 200 asking for supported tokens', async () => {
    patchGetWallet();
    patchGetTokenBySymbol();
    patchGetNativeBalance();
    patchGetERC20Balance();
    bsc.getContract = jest.fn().mockReturnValue({
      address: '0x242532ebDfcc760f2Ddfe8378eB51f5F847CE5bD',
    });

    await request(gatewayApp)
      .post(`/network/balances`)
      .send({
        chain: 'binance-smart-chain',
        network: 'testnet',
        address: '0x242532ebDfcc760f2Ddfe8378eB51f5F847CE5bD',
        tokenSymbols: ['WETH', 'DAI'],
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.balances.WETH).toBeDefined())
      .expect((res) => expect(res.body.balances.DAI).toBeDefined());
  });
});

describe('POST /evm/cancel', () => {
  it('should return 200', async () => {
    // override getWallet (network call)
    bsc.getWallet = jest.fn().mockReturnValue({
      address,
    });

    bsc.cancelTx = jest.fn().mockReturnValue({
      hash: '0xf6b9e7cec507cb3763a1179ff7e2a88c6008372e3a6f297d9027a0b39b0fff77', // noqa: mock
    });

    await request(gatewayApp)
      .post(`/evm/cancel`)
      .send({
        chain: 'binance-smart-chain',
        network: 'testnet',
        address,
        nonce: 23,
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200)
      .then((res: any) => {
        expect(res.body.txHash).toEqual(
          '0xf6b9e7cec507cb3763a1179ff7e2a88c6008372e3a6f297d9027a0b39b0fff77' // noqa: mock
        );
      });
  });

  it('should return 404 when parameters are invalid', async () => {
    await request(gatewayApp)
      .post(`/evm/cancel`)
      .send({
        chain: 'binance-smart-chain',
        network: 'testnet',
        address: '',
        nonce: '23',
      })
      .expect(404);
  });
});

describe('POST /network/poll', () => {
  it('should get a NETWORK_ERROR_CODE when the network is unavailable', async () => {
    patch(bsc, 'getCurrentBlockNumber', () => {
      const error: any = new Error('something went wrong');
      error.code = 'NETWORK_ERROR';
      throw error;
    });

    const res = await request(gatewayApp).post('/network/poll').send({
      chain: 'binance-smart-chain',
      network: 'testnet',
      txHash:
        '0xffdb7b393b46d3795b82c94b8d836ad6b3087a914244634fa89c3abbbf00ed72', // noqa: mock
    });

    expect(res.statusCode).toEqual(503);
    expect(res.body.errorCode).toEqual(NETWORK_ERROR_CODE);
    expect(res.body.message).toEqual(NETWORK_ERROR_MESSAGE);
  });

  it('should get a UNKNOWN_ERROR_ERROR_CODE when an unknown error is thrown', async () => {
    patch(bsc, 'getCurrentBlockNumber', () => {
      throw new Error();
    });

    const res = await request(gatewayApp).post('/network/poll').send({
      chain: 'binance-smart-chain',
      network: 'testnet',
      txHash:
        '0xffdb7b393b46d3795b82c94b8d836ad6b3087a914244634fa89c3abbbf00ed72', // noqa: mock
    });

    expect(res.statusCode).toEqual(503);
    expect(res.body.errorCode).toEqual(UNKNOWN_ERROR_ERROR_CODE);
  });

  it('should get an OUT of GAS error for failed out of gas transactions', async () => {
    patch(bsc, 'getCurrentBlockNumber', () => 1);
    patch(bsc, 'getTransaction', () => transactionOutOfGas);
    patch(bsc, 'getTransactionReceipt', () => transactionOutOfGasReceipt);
    const res = await request(gatewayApp).post('/network/poll').send({
      chain: 'binance-smart-chain',
      network: 'testnet',
      txHash:
        '0xffdb7b393b46d3795b82c94b8d836ad6b3087a914244634fa89c3abbbf00ed72', // noqa: mock
    });

    expect(res.statusCode).toEqual(503);
    expect(res.body.errorCode).toEqual(OUT_OF_GAS_ERROR_CODE);
    expect(res.body.message).toEqual(OUT_OF_GAS_ERROR_MESSAGE);
  });

  it('should get a null in txReceipt for Tx in the mempool', async () => {
    patch(bsc, 'getCurrentBlockNumber', () => 1);
    patch(bsc, 'getTransaction', () => transactionOutOfGas);
    patch(bsc, 'getTransactionReceipt', () => null);
    const res = await request(gatewayApp).post('/network/poll').send({
      chain: 'binance-smart-chain',
      network: 'testnet',
      txHash:
        '0xffdb7b393b46d3795b82c94b8d836ad6b3087a914244634fa89c3abbbf00ed72', // noqa: mock
    });
    expect(res.statusCode).toEqual(200);
    expect(res.body.txReceipt).toEqual(null);
    expect(res.body.txData).toBeDefined();
  });

  it('should get a null in txReceipt and txData for Tx that didnt reach the mempool and TxReceipt is null', async () => {
    patch(bsc, 'getCurrentBlockNumber', () => 1);
    patch(bsc, 'getTransaction', () => null);
    patch(bsc, 'getTransactionReceipt', () => null);
    const res = await request(gatewayApp).post('/network/poll').send({
      chain: 'binance-smart-chain',
      network: 'testnet',
      txHash:
        '0xffdb7b393b46d3795b82c94b8d836ad6b3087a914244634fa89c3abbbf00ed72', // noqa: mock
    });
    expect(res.statusCode).toEqual(200);
    expect(res.body.txReceipt).toEqual(null);
    expect(res.body.txData).toEqual(null);
  });

  it('should get txStatus = 1 for a succesful query', async () => {
    patch(bsc, 'getCurrentBlockNumber', () => 1);
    patch(bsc, 'getTransaction', () => transactionSuccesful);
    patch(bsc, 'getTransactionReceipt', () => transactionSuccesfulReceipt);
    const res = await request(gatewayApp).post('/network/poll').send({
      chain: 'binance-smart-chain',
      network: 'testnet',
      txHash:
        '0xffdb7b393b46d3795b82c94b8d836ad6b3087a914244634fa89c3abbbf00ed72', // noqa: mock
    });
    expect(res.statusCode).toEqual(200);
    expect(res.body.txReceipt).toBeDefined();
    expect(res.body.txData).toBeDefined();
  });

  it('should get unknown error', async () => {
    patch(bsc, 'getCurrentBlockNumber', () => {
      const error: any = new Error('something went wrong');
      error.code = -32006;
      throw error;
    });
    const res = await request(gatewayApp).post('/network/poll').send({
      chain: 'binance-smart-chain',
      network: 'testnet',
      txHash:
        '0xffdb7b393b46d3795b82c94b8d836ad6b3087a914244634fa89c3abbbf00ed72', // noqa: mock
    });
    expect(res.statusCode).toEqual(503);
    expect(res.body.errorCode).toEqual(UNKNOWN_ERROR_ERROR_CODE);
    expect(res.body.message).toEqual(UNKNOWN_ERROR_MESSAGE);
  });
});
