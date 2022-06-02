import request from 'supertest';
import { gatewayApp } from '../../src/app';
import { patch, unpatch } from '../services/patch';
import { Ethereum } from '../../src/chains/ethereum/ethereum';
import { Harmony } from '../../src/chains/harmony/harmony';
import { Avalanche } from '../../src/chains/avalanche/avalanche';
import { OverrideConfigs } from '../config.util';
import { patchEVMNonceManager } from '../evm.nonce.mock';

const overrideConfigs = new OverrideConfigs();
let eth: Ethereum;
let avalanche: Avalanche;
let harmony: Harmony;

beforeAll(async () => {
  await overrideConfigs.init();
  await overrideConfigs.updateConfigs();

  eth = Ethereum.getInstance('kovan');
  patchEVMNonceManager(eth.nonceManager);
  await eth.init();

  avalanche = Avalanche.getInstance('fuji');
  patchEVMNonceManager(avalanche.nonceManager);
  await avalanche.init();

  harmony = Harmony.getInstance('testnet');
  await harmony.init();
});

beforeEach(() => {
  patchEVMNonceManager(eth.nonceManager);
  patchEVMNonceManager(avalanche.nonceManager);
});

afterEach(async () => {
  unpatch();
});

afterAll(async () => {
  await eth.close();
  await avalanche.close();
  await harmony.close();
  await overrideConfigs.resetConfigs();
});

describe('GET /network/status', () => {
  it('should return 200 when asking for harmony network status', async () => {
    patch(harmony, 'chain', () => {
      return 'testnet';
    });
    patch(harmony, 'rpcUrl', 'http://...');
    patch(harmony, 'chainId', 88);
    patch(harmony, 'getCurrentBlockNumber', () => {
      return 3;
    });

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
    patch(eth, 'chain', () => {
      return 'kovan';
    });
    patch(eth, 'rpcUrl', 'http://...');
    patch(eth, 'chainId', 34);
    patch(eth, 'getCurrentBlockNumber', () => {
      return 1;
    });

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
    patch(avalanche, 'chain', () => {
      return 'fuji';
    });
    patch(avalanche, 'rpcUrl', 'http://...');
    patch(avalanche, 'chainId', 20);
    patch(avalanche, 'getCurrentBlockNumber', () => {
      return 2;
    });

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
    patch(eth, 'getCurrentBlockNumber', () => {
      return 212;
    });

    patch(avalanche, 'getCurrentBlockNumber', () => {
      return 204;
    });
    patch(harmony, 'getCurrentBlockNumber', () => {
      return 100;
    });

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

describe('GET /network/tokens', () => {
  it('should return 200 when retrieving tokens', async () => {
    await request(gatewayApp)
      .get(`/network/tokens`)
      .query({
        chain: 'ethereum',
        network: 'kovan',
      })
      .expect('Content-Type', /json/)
      .expect(200);
  });
  it('should return 200 when retrieving specific tokens', async () => {
    await request(gatewayApp)
      .get(`/network/tokens`)
      .query({
        chain: 'ethereum',
        network: 'kovan',
        tokenSymbols: ['COIN3', 'COIN1'],
      })
      .expect('Content-Type', /json/)
      .expect(200);
  });
  it('should return 500 when retrieving tokens for invalid chain', async () => {
    await request(gatewayApp)
      .get(`/network/tokens`)
      .query({
        chain: 'unknown',
        network: 'kovan',
      })
      .expect(500);
  });
});
