import request from 'supertest';
import { Injective } from '../../../src/chains/injective/injective';
import { patch, unpatch } from '../../services/patch';
import { gatewayApp } from '../../../src/app';
import { patchEVMNonceManager } from '../../evm.nonce.mock';

const TX_HASH =
  'CC6BF44223B4BD05396F83D55A0ABC0F16CE80836C0E34B08F4558CF72944299'; // noqa: mock
let injChain: Injective;

beforeAll(async () => {
  injChain = Injective.getInstance('mainnet');
  patchEVMNonceManager(injChain.nonceManager);
  patchCurrentBlockNumber();
  await injChain.init();
});

beforeEach(() => {
  patchEVMNonceManager(injChain.nonceManager);
  patchCurrentBlockNumber();
});

afterEach(() => {
  unpatch();
});

afterAll(async () => {
  await injChain.close();
});

const patchGetNonce = () => {
  patch(injChain.nonceManager, 'getNonce', () => 2);
};

const patchCommitNonce = () => {
  patch(injChain.nonceManager, 'commitNonce', () => 3);
};

const patchMsgBroadcaster = () => {
  patch(injChain, 'broadcaster', () => {
    return {
      broadcast() {
        return {
          txHash: TX_HASH,
        };
      },
    };
  });
};

const patchGetWallet = () => {
  patch(injChain, 'getWallet', () => {
    return {
      privateKey:
        '82683695dee0dc43536d4adf397b0dbff33e3f56adf036860e2002e57d6d5a3f', // noqa: mock
      injectiveAddress: 'inj1ycfk9k7pmqmst2craxteyd2k3xj93xuw2x0vgp',
      ethereumAddress: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
    };
  });
};

const patchCurrentBlockNumber = (withError: boolean = false) => {
  patch(injChain.chainRestTendermintApi, 'fetchLatestBlock', () => {
    return withError ? {} : { header: { height: 100 } };
  });
};

const patchBalances = () => {
  patch(injChain.chainRestBankApi, 'fetchBalances', () => {
    return { balances: [{ denom: 'INJ', amount: '1' }] };
  });
};

const patchGetTokenByDenom = () => {
  patch(injChain, 'getTokenByDenom', (symbol: string) => {
    let result;
    switch (symbol) {
      case 'INJ':
        result = {
          address: '0xd0A1E359811322d97991E03f863a0C30C2cFFFFF',
          chainId: 1,
          name: 'INJ',
          decimals: 1,
          symbol: 'INJ',
          denom: 'INJ',
        };
        break;
      case 'DAI':
        result = {
          chainId: 1,
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

const patchFetchTransaction = () => {
  const default_tx = {
    id: '',
    blockNumber: 4747419,
    blockTimestamp: '2022-05-03 15:38:17.443 +0000 UTC',
    hash: '0xd7a1c7ee985f807bf6bc06de728810fd52d85141549af0540486faf5e7de0d1d', // noqa: mock
    code: 0,
    data: 'CiMKIS9pbmplY3RpdmUuYXVjdGlvbi52MWJldGExLk1zZ0JpZA==',
    info: '',
    gasWanted: 400000,
    gasUsed: 99411,
    gasFee: {
      amountList: [
        {
          denom: 'inj',
          amount: '200000000000000',
        },
      ],
      gasLimit: 400000,
      payer: 'inj1hkhdaj2a2clmq5jq6mspsggqs32vynpk228q3r',
      granter: '',
    },
    codespace: '',
    eventsList: [],
    txType: 'injective',
    messages:
      '[{"type":"/injective.auction.v1beta1.MsgBid","value":{"bid_amount":{"amount":"1000000000000000000","denom":"inj"},"round":"15130","sender":"inj1hkhdaj2a2clmq5jq6mspsggqs32vynpk228q3r"}}]',
    signatures: [
      {
        pubkey: 'injvalcons1hkhdaj2a2clmq5jq6mspsggqs32vynpkflpeux',
        address: 'inj1hkhdaj2a2clmq5jq6mspsggqs32vynpk228q3r',
        sequence: 1120,
        signature:
          'jUkld9DBYu8DgwWr+OCMfbcIww5wtxrY4jrpXGL7GHY1nE415fKRZhWhfVV8P4Wx5OQWnZjYnfUSIKQq0m3QgQ==',
      },
    ],
    memo: '',
  };
  patch(injChain, 'poll', () => {
    return default_tx;
  });
};

describe('GET /injective/block/current', () => {
  it('should return 200 with correct params', async () => {
    patchCurrentBlockNumber();
    await request(gatewayApp)
      .get(`/injective/block/current`)
      .query({
        chain: 'injective',
        network: 'mainnet',
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body).toEqual(100));
  });

  it('should return 503 when network is not ready', async () => {
    patchCurrentBlockNumber(true);
    await request(gatewayApp)
      .get(`/injective/block/current`)
      .query({
        chain: 'injective',
        network: 'mainnet',
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(503);
  });

  it('should return 503 when parameters are invalid', async () => {
    await request(gatewayApp)
      .get(`/injective/block/current`)
      .query({
        chain: 123,
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(503);
  });
});

describe('POST /injective/transfer/to/bank', () => {
  it('should return 200 with proper request params', async () => {
    patchGetWallet();
    patchCommitNonce();
    patchGetNonce();
    patchMsgBroadcaster();
    patchCurrentBlockNumber();
    await request(gatewayApp)
      .post(`/injective/transfer/to/bank`)
      .send({
        chain: 'injective',
        network: 'mainnet',
        address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
        subaccountId: '000000000000000000000000',
        amount: '100',
        token: 'INJ',
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body).toEqual(TX_HASH));
  });

  it('should return 404 when parameters are invalid/incomplete', async () => {
    await request(gatewayApp)
      .post(`/injective/transfer/to/bank`)
      .send({
        chain: 'injective',
        network: 'mainnet',
      })
      .expect(404);
  });
});

describe('POST /injective/transfer/to/sub', () => {
  it('should return 200 with correct parameters', async () => {
    patchGetWallet();
    patchCommitNonce();
    patchGetNonce();
    patchMsgBroadcaster();

    await request(gatewayApp)
      .post(`/injective/transfer/to/sub`)
      .send({
        chain: 'injective',
        network: 'mainnet',
        address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
        subaccountId: '000000000000000000000000',
        amount: '100',
        token: 'INJ',
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body).toEqual(TX_HASH));
  });

  it('should return 404 when parameters are invalid/incomplete', async () => {
    await request(gatewayApp)
      .post(`/injective/transfer/to/sub`)
      .send({
        chain: 'injective',
        network: 'mainnet',
      })
      .expect(404);
  });
});

describe('POST /injective/balances', () => {
  it('should return 200 with correct parameters', async () => {
    patchGetWallet();
    patchGetTokenByDenom();
    patchBalances();
    patchCurrentBlockNumber();

    await request(gatewayApp)
      .post(`/injective/balances`)
      .send({
        chain: 'injective',
        network: 'mainnet',
        address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200);
    //.expect((res) => expect(res.body.nonce).toBe(3));
  });

  it('should return 404 when parameters are invalid/incomplete', async () => {
    await request(gatewayApp)
      .post(`/injective/balances`)
      .send({
        chain: 'injective',
        network: 'mainnet',
      })
      .expect(404);
  });
});

describe('POST /injective/poll', () => {
  it('should return 200 with correct parameters', async () => {
    patchFetchTransaction();
    const res = await request(gatewayApp).post('/injective/poll').send({
      chain: 'injective',
      network: 'mainnet',
      txHash:
        '0x2faeb1aa55f96c1db55f643a8cf19b0f76bf091d0b7d1b068d2e829414576362', // noqa: mock
    });
    expect(res.statusCode).toEqual(200);
  });

  it('should get unknown error with invalid txHash', async () => {
    const res = await request(gatewayApp).post('/injective/poll').send({
      chain: 'injective',
      network: 'mainnet',
      txHash: 123,
    });
    expect(res.statusCode).toEqual(404);
  });
});
