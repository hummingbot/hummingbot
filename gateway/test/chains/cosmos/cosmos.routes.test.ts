import request from 'supertest';
import { patch, unpatch } from '../../services/patch';
import { gatewayApp } from '../../../src/app';
import { publicKey } from './cosmos.validators.test';
import * as getTransactionData from './fixtures/getTransaction.json';
import { BigNumber } from 'ethers';
import { Cosmos } from '../../../src/chains/cosmos/cosmos';
const { decodeTxRaw } = require('@cosmjs/proto-signing');

let cosmos: Cosmos;

const tokens = ['ATOM', 'AXS'];

beforeAll(async () => {
  cosmos = Cosmos.getInstance('testnet');
  await cosmos.init();
});

afterEach(() => unpatch());

describe('GET /cosmos', () => {
  it('should return 200', async () => {
    await request(gatewayApp)
      .get(`/cosmos`)
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.connection).toBe(true))
      .expect((res) => expect(res.body.rpcUrl).toBe(cosmos.rpcUrl));
  });
});

const patchGetBalances = () => {
  patch(cosmos, 'getBalances', () => {
    return {
      [tokens[0]]: { value: BigNumber.from(228293), decimals: 9 },
      [tokens[1]]: { value: BigNumber.from(300003), decimals: 9 },
    };
  });
};

const patchGetWallet = () => {
  patch(cosmos, 'getWallet', () => {
    return {
      address: publicKey,
      prefix: 'cosmos',
    };
  });
};

describe('POST /cosmos/balances', () => {
  it('should return 200', async () => {
    patchGetWallet();
    patchGetBalances();

    await request(gatewayApp)
      .post(`/cosmos/balances`)
      .send({ address: publicKey, tokenSymbols: tokens, network: cosmos.chain })
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.network).toBe(cosmos.chain))
      .expect((res) => expect(res.body.timestamp).toBeNumber())
      .expect((res) => expect(res.body.latency).toBeNumber())
      .expect((res) =>
        expect(res.body.balances).toEqual({
          [tokens[0]]: '0.000228293',
          [tokens[1]]: '0.000300003',
        })
      );
  });

  it('should return 500 when asking for an unsupported token', async () => {
    patchGetWallet();
    patchGetBalances();

    await request(gatewayApp)
      .post(`/cosmos/balances`)
      .send({
        address: publicKey,
        tokenSymbols: ['AXSS'],
        network: cosmos.chain,
      })
      .expect(500);
  });

  it('should return 404 when parameters are invalid', async () => {
    await request(gatewayApp).post(`/cosmos/balances`).send({}).expect(404);
  });
});

const CurrentBlockNumber = 11829933;
const patchGetCurrentBlockNumber = () => {
  patch(cosmos, 'getCurrentBlockNumber', () => CurrentBlockNumber);
};

const patchGetTransaction = () => {
  patch(cosmos, 'getTransaction', () => getTransactionData);
};

const txHash =
  'F499E2C489FAF5C8E575650666EE8934963DF15E7850E710179BB4C00713C190'; // noqa: mock

describe('POST /cosmos/poll', () => {
  it('should return 200', async () => {
    patchGetCurrentBlockNumber();
    patchGetTransaction();

    await request(gatewayApp)
      .post(`/cosmos/poll`)
      .send({
        txHash,
        network: cosmos.chain,
      })
      .expect('Content-Type', /json/)
      .expect((res) => expect(res.body.network).toBe(cosmos.chain))
      .expect(200)
      .expect((res) => expect(res.body.timestamp).toBeNumber())
      .expect((res) => expect(res.body.currentBlock).toBe(CurrentBlockNumber))
      .expect((res) => expect(res.body.txHash).toBe(txHash))
      .expect((res) =>
        expect(res.body.txData).toEqual(decodeTxRaw(getTransactionData.tx))
      );
  });

  it('should return 404 when parameters are invalid', async () => {
    await request(gatewayApp).post(`/cosmos/poll`).send({}).expect(404);
  });
});
