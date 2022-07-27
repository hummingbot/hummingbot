import request from 'supertest';
import { Ethereum } from '../../../src/chains/ethereum/ethereum';
import { patch, unpatch } from '../../services/patch';
import { gatewayApp } from '../../../src/app';
import {
  NETWORK_ERROR_CODE,
  RATE_LIMIT_ERROR_CODE,
  OUT_OF_GAS_ERROR_CODE,
  UNKNOWN_ERROR_ERROR_CODE,
  NETWORK_ERROR_MESSAGE,
  RATE_LIMIT_ERROR_MESSAGE,
  OUT_OF_GAS_ERROR_MESSAGE,
  UNKNOWN_ERROR_MESSAGE,
} from '../../../src/services/error-handler';
import { patchEVMNonceManager } from '../../evm.nonce.mock';
import * as transactionSuccesful from './fixtures/transaction-succesful.json';
import * as transactionSuccesfulReceipt from './fixtures/transaction-succesful-receipt.json';
import * as transactionOutOfGas from './fixtures/transaction-out-of-gas.json';
import * as transactionOutOfGasReceipt from './fixtures/transaction-out-of-gas-receipt.json';
let eth: Ethereum;

beforeAll(async () => {
  eth = Ethereum.getInstance('kovan');
  patchEVMNonceManager(eth.nonceManager);
  await eth.init();
});

beforeEach(() => {
  patchEVMNonceManager(eth.nonceManager);
});

afterEach(() => {
  unpatch();
});

afterAll(async () => {
  await eth.close();
});

const patchGetWallet = () => {
  patch(eth, 'getWallet', () => {
    return {
      address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
    };
  });
};

const patchGetNonce = () => {
  patch(eth.nonceManager, 'getNonce', () => 2);
};

const patchGetNextNonce = () => {
  patch(eth.nonceManager, 'getNextNonce', () => 3);
};

const patchGetERC20Balance = () => {
  patch(eth, 'getERC20Balance', () => ({ value: 1, decimals: 3 }));
};

const patchGetNativeBalance = () => {
  patch(eth, 'getNativeBalance', () => ({ value: 1, decimals: 3 }));
};

const patchGetERC20Allowance = () => {
  patch(eth, 'getERC20Allowance', () => ({ value: 1, decimals: 3 }));
};

const patchGetTokenBySymbol = () => {
  patch(eth, 'getTokenBySymbol', (symbol: string) => {
    let result;
    switch (symbol) {
      case 'WETH':
        result = {
          chainId: 42,
          name: 'WETH',
          symbol: 'WETH',
          address: '0xd0A1E359811322d97991E03f863a0C30C2cF029C',
          decimals: 18,
        };
        break;
      case 'DAI':
        result = {
          chainId: 42,
          name: 'DAI',
          symbol: 'DAI',
          address: '0xd0A1E359811322d97991E03f863a0C30C2cFFFFF',
          decimals: 18,
        };
        break;
    }
    return result;
  });
};

const patchApproveERC20 = (tx_type?: string) => {
  const default_tx = {
    type: 2,
    chainId: 42,
    nonce: 115,
    maxPriorityFeePerGas: { toString: () => '106000000000' },
    maxFeePerGas: { toString: () => '106000000000' },
    gasPrice: { toString: () => null },
    gasLimit: { toString: () => '100000' },
    to: '0x4F96Fe3b7A6Cf9725f59d353F723c1bDb64CA6Aa',
    value: { toString: () => '0' },
    data: '0x095ea7b30000000000000000000000007a250d5630b4cf539739df2c5dacb4c659f2488dffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff', // noqa: mock
    accessList: [],
    hash: '0x75f98675a8f64dcf14927ccde9a1d59b67fa09b72cc2642ad055dae4074853d9', // noqa: mock
    v: 0,
    r: '0xbeb9aa40028d79b9fdab108fcef5de635457a05f3a254410414c095b02c64643', // noqa: mock
    s: '0x5a1506fa4b7f8b4f3826d8648f27ebaa9c0ee4bd67f569414b8cd8884c073100', // noqa: mock
    from: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
    confirmations: 0,
  };
  if (tx_type === 'overwritten_tx') {
    default_tx.hash =
      '0x5a1ed682d0d7a58fbd7828bbf5994cd024feb8895d4da82c741ec4a191b9e849'; // noqa: mock
  }
  patch(eth, 'approveERC20', () => {
    return default_tx;
  });
};

describe('POST /evm/allowances', () => {
  it('should return 200 asking for allowances', async () => {
    patchGetWallet();
    patchGetTokenBySymbol();
    const theSpender = '0xFaA12FD102FE8623C9299c72B03E45107F2772B5';
    eth.getSpender = jest.fn().mockReturnValue(theSpender);
    eth.getContract = jest.fn().mockReturnValue({
      address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
    });
    patchGetERC20Allowance();

    await request(gatewayApp)
      .post(`/evm/allowances`)
      .send({
        chain: 'ethereum',
        network: 'kovan',
        address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
        spender: theSpender,
        tokenSymbols: ['WETH', 'DAI'],
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.spender).toEqual(theSpender))
      .expect((res) => expect(res.body.approvals.WETH).toEqual('0.001'))
      .expect((res) => expect(res.body.approvals.DAI).toEqual('0.001'));
  });

  it('should return 404 when parameters are invalid', async () => {
    await request(gatewayApp)
      .post(`/evm/allowances`)
      .send({
        chain: 'ethereum',
        network: 'kovan',
        address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
        spender: '0xSpender',
        tokenSymbols: ['WETH', 'DAI'],
      })
      .expect(404);
  });
});

describe('POST /network/balances', () => {
  it('should return 200 asking for supported tokens', async () => {
    patchGetWallet();
    patchGetTokenBySymbol();
    patchGetNativeBalance();
    patchGetERC20Balance();
    eth.getContract = jest.fn().mockReturnValue({
      address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
    });

    await request(gatewayApp)
      .post(`/network/balances`)
      .send({
        chain: 'ethereum',
        network: 'kovan',
        address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
        tokenSymbols: ['WETH', 'DAI'],
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.balances.WETH).toBeDefined())
      .expect((res) => expect(res.body.balances.DAI).toBeDefined());
  });

  it('should return 200 asking for native token', async () => {
    patchGetWallet();
    patchGetTokenBySymbol();
    patchGetNativeBalance();
    patchGetERC20Balance();
    eth.getContract = jest.fn().mockReturnValue({
      address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
    });

    await request(gatewayApp)
      .post(`/network/balances`)
      .send({
        chain: 'ethereum',
        network: 'kovan',
        address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
        tokenSymbols: ['ETH'],
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.balances.ETH).toBeDefined())
      .expect((res) => console.log(res.body));
  });

  it('should return 500 for unsupported tokens', async () => {
    patchGetWallet();
    patchGetTokenBySymbol();
    patchGetNativeBalance();
    patchGetERC20Balance();
    eth.getContract = jest.fn().mockReturnValue({
      address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
    });

    await request(gatewayApp)
      .post(`/network/balances`)
      .send({
        chain: 'ethereum',
        network: 'kovan',
        address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
        tokenSymbols: ['XXX', 'YYY'],
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(500);
  });

  it('should return 404 when parameters are invalid', async () => {
    await request(gatewayApp)
      .post(`/network/balances`)
      .send({
        chain: 'ethereum',
        network: 'kovan',
        address: 'da857cbda0ba96757fed842617a4',
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
        chain: 'ethereum',
        network: 'kovan',
        address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.nonce).toBe(2));
  });

  it('should return 404 when parameters are invalid', async () => {
    await request(gatewayApp)
      .post(`/evm/nonce`)
      .send({
        chain: 'ethereum',
        network: 'kovan',
        address: 'da857cbda0ba96757fed842617a4',
      })
      .expect(404);
  });
});

describe('POST /evm/nextNonce', () => {
  it('should return 200', async () => {
    patchGetWallet();
    patchGetNextNonce();

    await request(gatewayApp)
      .post(`/evm/nextNonce`)
      .send({
        chain: 'ethereum',
        network: 'kovan',
        address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.nonce).toBe(3));
  });

  it('should return 404 when parameters are invalid', async () => {
    await request(gatewayApp)
      .post(`/evm/nextNonce`)
      .send({
        chain: 'ethereum',
        network: 'kovan',
        address: 'da857cbda0ba96757fed842617a4',
      })
      .expect(404);
  });
});

describe('POST /evm/approve', () => {
  it('approve without nonce parameter should return 200', async () => {
    patchGetWallet();
    eth.getContract = jest.fn().mockReturnValue({
      address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
    });
    patch(eth.nonceManager, 'getNonce', () => 115);
    patchGetTokenBySymbol();
    patchApproveERC20();

    await request(gatewayApp)
      .post(`/evm/approve`)
      .send({
        chain: 'ethereum',
        network: 'kovan',
        address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
        spender: 'uniswap',
        token: 'WETH',
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200);
  });

  it('approve with nonce parameter should return 200', async () => {
    patchGetWallet();
    patch(eth.nonceManager, 'getNonce', () => 115);
    patchGetTokenBySymbol();
    patchApproveERC20();

    await request(gatewayApp)
      .post(`/evm/approve`)
      .send({
        chain: 'ethereum',
        network: 'kovan',
        address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
        spender: 'uniswap',
        token: 'WETH',
        nonce: 115,
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200)
      .then((res: any) => {
        expect(res.body.nonce).toEqual(115);
      });
  });

  it('approve with maxFeePerGas and maxPriorityFeePerGas should return 200', async () => {
    patchGetWallet();
    patch(eth.nonceManager, 'getNonce', () => 115);
    patchGetTokenBySymbol();
    patchApproveERC20();

    await request(gatewayApp)
      .post(`/evm/approve`)
      .send({
        chain: 'ethereum',
        network: 'kovan',
        address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
        spender: 'uniswap',
        token: 'WETH',
        nonce: 115,
        maxFeePerGas: '5000000000',
        maxPriorityFeePerGas: '5000000000',
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200);
  });

  it('should return 404 when parameters are invalid', async () => {
    await request(gatewayApp)
      .post(`/evm/approve`)
      .send({
        chain: 'ethereum',
        network: 'kovan',
        address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
        spender: 'uniswap',
        token: 123,
        nonce: '23',
      })
      .expect(404);
  });
});

describe('POST /evm/cancel', () => {
  it('should return 200', async () => {
    // override getWallet (network call)
    eth.getWallet = jest.fn().mockReturnValue({
      address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
    });

    eth.cancelTx = jest.fn().mockReturnValue({
      hash: '0xf6b9e7cec507cb3763a1179ff7e2a88c6008372e3a6f297d9027a0b39b0fff77', // noqa: mock
    });

    await request(gatewayApp)
      .post(`/evm/cancel`)
      .send({
        chain: 'ethereum',
        network: 'kovan',
        address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
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
        chain: 'ethereum',
        network: 'kovan',
        address: '',
        nonce: '23',
      })
      .expect(404);
  });
});

describe('POST /network/poll', () => {
  it('should get a NETWORK_ERROR_CODE when the network is unavailable', async () => {
    patch(eth, 'getCurrentBlockNumber', () => {
      const error: any = new Error('something went wrong');
      error.code = 'NETWORK_ERROR';
      throw error;
    });

    const res = await request(gatewayApp).post('/network/poll').send({
      chain: 'ethereum',
      network: 'kovan',
      txHash:
        '0x2faeb1aa55f96c1db55f643a8cf19b0f76bf091d0b7d1b068d2e829414576362', // noqa: mock
    });

    expect(res.statusCode).toEqual(503);
    expect(res.body.errorCode).toEqual(NETWORK_ERROR_CODE);
    expect(res.body.message).toEqual(NETWORK_ERROR_MESSAGE);
  });

  it('should get a UNKNOWN_ERROR_ERROR_CODE when an unknown error is thrown', async () => {
    patch(eth, 'getCurrentBlockNumber', () => {
      throw new Error();
    });

    const res = await request(gatewayApp).post('/network/poll').send({
      txHash:
        '0x2faeb1aa55f96c1db55f643a8cf19b0f76bf091d0b7d1b068d2e829414576362', // noqa: mock
    });

    expect(res.statusCode).toEqual(503);
    expect(res.body.errorCode).toEqual(UNKNOWN_ERROR_ERROR_CODE);
  });

  it('should get an OUT of GAS error for failed out of gas transactions', async () => {
    patch(eth, 'getCurrentBlockNumber', () => 1);
    patch(eth, 'getTransaction', () => transactionOutOfGas);
    patch(eth, 'getTransactionReceipt', () => transactionOutOfGasReceipt);
    const res = await request(gatewayApp).post('/network/poll').send({
      chain: 'ethereum',
      network: 'kovan',
      txHash:
        '0x2faeb1aa55f96c1db55f643a8cf19b0f76bf091d0b7d1b068d2e829414576362', // noqa: mock
    });

    expect(res.statusCode).toEqual(503);
    expect(res.body.errorCode).toEqual(OUT_OF_GAS_ERROR_CODE);
    expect(res.body.message).toEqual(OUT_OF_GAS_ERROR_MESSAGE);
  });

  it('should get a null in txReceipt for Tx in the mempool', async () => {
    patch(eth, 'getCurrentBlockNumber', () => 1);
    patch(eth, 'getTransaction', () => transactionOutOfGas);
    patch(eth, 'getTransactionReceipt', () => null);
    const res = await request(gatewayApp).post('/network/poll').send({
      chain: 'ethereum',
      network: 'kovan',
      txHash:
        '0x2faeb1aa55f96c1db55f643a8cf19b0f76bf091d0b7d1b068d2e829414576362', // noqa: mock
    });
    expect(res.statusCode).toEqual(200);
    expect(res.body.txReceipt).toEqual(null);
    expect(res.body.txData).toBeDefined();
  });

  it('should get a null in txReceipt and txData for Tx that didnt reach the mempool and TxReceipt is null', async () => {
    patch(eth, 'getCurrentBlockNumber', () => 1);
    patch(eth, 'getTransaction', () => null);
    patch(eth, 'getTransactionReceipt', () => null);
    const res = await request(gatewayApp).post('/network/poll').send({
      chain: 'ethereum',
      network: 'kovan',
      txHash:
        '0x2faeb1aa55f96c1db55f643a8cf19b0f76bf091d0b7d1b068d2e829414576362', // noqa: mock
    });
    expect(res.statusCode).toEqual(200);
    expect(res.body.txReceipt).toEqual(null);
    expect(res.body.txData).toEqual(null);
  });

  it('should get txStatus = 1 for a succesful query', async () => {
    patch(eth, 'getCurrentBlockNumber', () => 1);
    patch(eth, 'getTransaction', () => transactionSuccesful);
    patch(eth, 'getTransactionReceipt', () => transactionSuccesfulReceipt);
    const res = await request(gatewayApp).post('/network/poll').send({
      chain: 'ethereum',
      network: 'kovan',
      txHash:
        '0x6d068067a5e5a0f08c6395b31938893d1cdad81f54a54456221ecd8c1941294d', // noqa: mock
    });
    expect(res.statusCode).toEqual(200);
    expect(res.body.txReceipt).toBeDefined();
    expect(res.body.txData).toBeDefined();
  });

  it('should get an RATE_LIMIT_ERROR_CODE when the blockchain API is rate limited', async () => {
    patch(eth, 'getCurrentBlockNumber', () => {
      const error: any = new Error(
        'daily request count exceeded, request rate limited'
      );
      error.code = -32005;
      error.data = {
        see: 'https://infura.io/docs/ethereum/jsonrpc/ratelimits',
        current_rps: 13.333,
        allowed_rps: 10.0,
        backoff_seconds: 30.0,
      };
      throw error;
    });
    const res = await request(gatewayApp).post('/network/poll').send({
      chain: 'ethereum',
      network: 'kovan',
      txHash:
        '0x2faeb1aa55f96c1db55f643a8cf19b0f76bf091d0b7d1b068d2e829414576362', // noqa: mock
    });
    expect(res.statusCode).toEqual(503);
    expect(res.body.errorCode).toEqual(RATE_LIMIT_ERROR_CODE);
    expect(res.body.message).toEqual(RATE_LIMIT_ERROR_MESSAGE);
  });

  it('should get unknown error', async () => {
    patch(eth, 'getCurrentBlockNumber', () => {
      const error: any = new Error('something went wrong');
      error.code = -32006;
      throw error;
    });
    const res = await request(gatewayApp).post('/network/poll').send({
      chain: 'ethereum',
      network: 'kovan',
      txHash:
        '0x2faeb1aa55f96c1db55f643a8cf19b0f76bf091d0b7d1b068d2e829414576362', // noqa: mock
    });
    expect(res.statusCode).toEqual(503);
    expect(res.body.errorCode).toEqual(UNKNOWN_ERROR_ERROR_CODE);
    expect(res.body.message).toEqual(UNKNOWN_ERROR_MESSAGE);
  });
});

describe('overwrite existing transaction', () => {
  it('overwritten transaction is dropped', async () => {
    patchGetWallet();
    patch(eth.nonceManager, 'getNonce', () => 115);
    patchGetTokenBySymbol();

    const requestParam = {
      chain: 'ethereum',
      network: 'kovan',
      address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
      spender: 'uniswap',
      token: 'WETH',
      nonce: 115,
      maxFeePerGas: '5000000000',
      maxPriorityFeePerGas: '5000000000',
    };

    patchApproveERC20('overwritten_tx');
    const tx_1 = await request(gatewayApp)
      .post(`/evm/approve`)
      .send(requestParam)
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200);

    patchApproveERC20(); // patch to return different tx_hash
    requestParam.maxPriorityFeePerGas = '8000000000'; // we only increase maxPriorityFeePerGas
    const tx_2 = await request(gatewayApp)
      .post(`/evm/approve`)
      .send(requestParam)
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200);

    // once tx_2 is confirmed, tx_1 will be dropped
    patch(eth, 'getCurrentBlockNumber', () => 1);
    patch(eth, 'getTransaction', () => null);
    patch(eth, 'getTransactionReceipt', () => null);
    const res_1 = await request(gatewayApp).post('/network/poll').send({
      chain: 'ethereum',
      network: 'kovan',
      txHash: tx_1.body.approval.hash,
    });
    expect(res_1.statusCode).toEqual(200);
    expect(res_1.body.txReceipt).toEqual(null);
    expect(res_1.body.txData).toEqual(null);

    patch(eth, 'getCurrentBlockNumber', () => 1);
    patch(eth, 'getTransaction', () => transactionSuccesful);
    patch(eth, 'getTransactionReceipt', () => transactionSuccesfulReceipt);
    const res_2 = await request(gatewayApp).post('/network/poll').send({
      chain: 'ethereum',
      network: 'kovan',
      txHash: tx_2.body.approval.hash,
    });
    expect(res_2.statusCode).toEqual(200);
    expect(res_2.body.txReceipt).toBeDefined();
    expect(res_2.body.txData).toBeDefined();
  });
});
