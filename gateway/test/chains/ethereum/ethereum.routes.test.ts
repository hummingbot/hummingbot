import express from 'express';
import { Express } from 'express-serve-static-core';
import request from 'supertest';
import { EthereumRoutes } from '../../../src/chains/ethereum/ethereum.routes';

let app: Express;

beforeAll(async () => {
  app = express();
  app.use(express.json());
  app.use('/eth', EthereumRoutes.router);
});

describe('GET /eth', () => {
  it('should return 200', async () => {
    request(app).get(`/eth`).expect('Content-Type', /json/).expect(200);
  });
});

describe('POST /eth/nonce', () => {
  it('should return 200', async () => {
    EthereumRoutes.ethereum.getWallet = jest.fn().mockReturnValue(() => {
      address: '0x0000000000000000000';
    });
    EthereumRoutes.ethereum.nonceManager.getNonce = jest
      .fn()
      .mockReturnValue(() => Promise.resolve(2));
    const res = await request(app)
      .post(`/eth/nonce`)
      .send({ privateKey: 'abc123' })
      .set('Accept', 'application/json');
    expect(res.statusCode).toEqual(200);
  });
});
