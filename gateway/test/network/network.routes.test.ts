import request from 'supertest';
import { gatewayApp } from '../../src/app';

describe('GET /network/status', () => {
  it('should return 200 when asking for harmony network status', async () => {
    await request(gatewayApp)
      .get(`/network/status`)
      .query({
        chain: 'harmony',
        network: 'testnet',
      })
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.chain).toBe('testnet'))
      .expect((res) => expect(res.body.chainId).toBeDefined())
      .expect((res) => expect(res.body.rpcUrl).toBeDefined())
      .expect((res) => expect(res.body.currentBlockNumber).toBeDefined());
  });

  it('should return 200 when asking for ethereum network status', async () => {
    await request(gatewayApp)
      .get(`/network/status`)
      .query({
        chain: 'ethereum',
        network: 'kovan',
      })
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.chain).toBe('kovan'))
      .expect((res) => expect(res.body.chainId).toBeDefined())
      .expect((res) => expect(res.body.rpcUrl).toBeDefined())
      .expect((res) => expect(res.body.currentBlockNumber).toBeDefined());
  });

  it('should return 200 when asking for avalance network status', async () => {
    await request(gatewayApp)
      .get(`/network/status`)
      .query({
        chain: 'avalanche',
        network: 'fuji',
      })
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.chain).toBe('fuji'))
      .expect((res) => expect(res.body.chainId).toBeDefined())
      .expect((res) => expect(res.body.rpcUrl).toBeDefined())
      .expect((res) => expect(res.body.currentBlockNumber).toBeDefined());
  });

  it('should return 200 when requesting network status without specifying', async () => {
    await request(gatewayApp)
      .get(`/network/status`)
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(Array.isArray(res.body)).toEqual(true));
  });

  it('should return 500 when asking for invalid network', async () => {
    await request(gatewayApp)
      .get(`/network/status`)
      .query({
        chain: 'hello',
      })
      .expect(500);
  });
});

describe('GET /network/config', () => {
  it('should return 200 when asking for config', async () => {
    request(gatewayApp)
      .get(`/network/config`)
      .expect('Content-Type', /json/)
      .expect(200);
  });
});
