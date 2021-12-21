import request from 'supertest';
import { patch, unpatch } from '../../services/patch';
import { app } from '../../../src/app';
import { Solana } from '../../../src/chains/solana/solana';
import { privateKey, publicKey } from './solana.validators.test';
import { tokenSymbols } from '../../services/validators.test';
import bs58 from 'bs58';

let solana: Solana;
beforeAll(async () => {
  solana = Solana.getInstance();
  await solana.init();
});

afterEach(() => unpatch());

describe('GET /solana', () => {
  it('should return 200', async () => {
    request(app)
      .get(`/solana`)
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.connection).toBe(true))
      .expect((res) => expect(res.body.rpcUrl).toBe(solana.rpcUrl));
  });
});

const patchGetWallet = () => {
  patch(solana, 'getWallet', () => {
    return {
      publicKey: bs58.decode(publicKey),
      secretKey: bs58.decode(privateKey),
    };
  });
};

const patchGetBalances = () => {
  patch(solana, 'getBalances', () => {
    return {
      [tokenSymbols[0]]: { value: 1, decimals: 1 },
      [tokenSymbols[1]]: { value: 2, decimals: 2 },
      OTH: { value: 3, decimals: 3 },
    };
  });
};

describe('POST /solana/balance', () => {
  it('should return 200', async () => {
    patchGetWallet();
    patchGetBalances();

    await request(app)
      .post(`/solana/balance`)
      .send({ privateKey, tokenSymbols })
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.network).toBe(solana.cluster))
      .expect((res) => expect(res.body.timestamp).toBeNumber())
      .expect((res) => expect(res.body.latency).toBeNumber())
      .expect((res) =>
        expect(res.body.balances).toEqual({
          [tokenSymbols[0]]: '0.1',
          [tokenSymbols[1]]: '0.02',
        })
      );
  });

  it('should return 404 when parameters are invalid', async () => {
    await request(app).post(`/solana/balance`).send({}).expect(404);
  });
});

describe('GET /solana/token', () => {
  it('should return 404 when parameters are invalid', async () => {
    await request(app).get(`/solana/token`).send({}).expect(404);
  });
});

describe('POST /solana/token', () => {
  it('should return 404 when parameters are invalid', async () => {
    await request(app).post(`/solana/token`).send({}).expect(404);
  });
});

describe('POST /solana/poll', () => {
  it('should return 404 when parameters are invalid', async () => {
    await request(app).post(`/solana/poll`).send({}).expect(404);
  });
});
