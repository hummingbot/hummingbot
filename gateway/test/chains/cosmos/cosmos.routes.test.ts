import request from 'supertest';
import { patch, unpatch } from '../../services/patch';
import { gatewayApp } from '../../../src/app';
import { publicKey } from './cosmos.validators.test';
import * as getTransactionData from './fixtures/getTransaction.json';
import { BigNumber } from 'ethers';
import { Cosmos } from '../../../src/chains/cosmos/cosmos';
import { CosmosConfig } from '../../../src/chains/cosmos/cosmos.config';
const { decodeTxRaw } = require('@cosmjs/proto-signing');

let cosmos: Cosmos;

const tokens = ['ATOM', 'AXS'];

beforeAll(async () => {
  cosmos = Cosmos.getInstance('mainnet');
  await cosmos.init();
});

afterEach(() => unpatch());

describe('GET /cosmos', () => {
  it('should return 200', async () => {
    request(gatewayApp)
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
    };
  });
};

describe('POST /cosmos/balances', () => {
  it('should return 200', async () => {
    patchGetWallet();
    patchGetBalances();

    await request(gatewayApp)
      .post(`/cosmos/balances`)
      .send({ address: publicKey, tokenSymbols: tokens })
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) =>
        expect(res.body.network).toBe(CosmosConfig.config.network.name)
      )
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
      .send({ address: publicKey, tokenSymbols: ['AXSS'] })
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
  '43785B183B154C3701CD62C07187CBFBE0A938B27D032094FBE9F9FA288BC6ED'; // noqa: mock

describe('POST /cosmos/poll', () => {
  it('should return 200', async () => {
    patchGetCurrentBlockNumber();
    patchGetTransaction();

    await request(gatewayApp)
      .post(`/cosmos/poll`)
      .send({
        txHash,
      })
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) =>
        expect(res.body.network).toBe(CosmosConfig.config.network.name)
      )
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
