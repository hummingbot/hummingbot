import request from 'supertest';
import { unpatch } from '../../services/patch';
import { app } from '../../../src/app';
import { Solana } from '../../../src/chains/solana/solana';

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

describe('POST /solana/balance', () => {
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
