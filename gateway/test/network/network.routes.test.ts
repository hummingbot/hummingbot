import request from 'supertest';
import { gatewayApp } from '../../src/app';
import { Avalanche } from '../../src/chains/avalanche/avalanche';
import { Cronos } from '../../src/chains/cronos/cronos';
import { Ethereum } from '../../src/chains/ethereum/ethereum';
import { Harmony } from '../../src/chains/harmony/harmony';
import { Polygon } from '../../src/chains/polygon/polygon';
import { patchEVMNonceManager } from '../evm.nonce.mock';
import { patch, unpatch } from '../services/patch';
let eth: Ethereum;
let goerli: Ethereum;
let avalanche: Avalanche;
let harmony: Harmony;
let polygon: Polygon;
let cronos: Cronos;

beforeAll(async () => {
  eth = Ethereum.getInstance('kovan');
  patchEVMNonceManager(eth.nonceManager);
  await eth.init();

  goerli = Ethereum.getInstance('goerli');
  patchEVMNonceManager(goerli.nonceManager);
  await goerli.init();

  avalanche = Avalanche.getInstance('fuji');
  patchEVMNonceManager(avalanche.nonceManager);
  await avalanche.init();

  harmony = Harmony.getInstance('testnet');
  await harmony.init();

  polygon = Polygon.getInstance('mumbai');
  await polygon.init();

  cronos = Cronos.getInstance('testnet');
  await cronos.init();
});

beforeEach(() => {
  patchEVMNonceManager(eth.nonceManager);
  patchEVMNonceManager(goerli.nonceManager);
  patchEVMNonceManager(avalanche.nonceManager);
  patchEVMNonceManager(harmony.nonceManager);
  patchEVMNonceManager(polygon.nonceManager);
  patchEVMNonceManager(cronos.nonceManager);
});

afterEach(async () => {
  unpatch();
});

afterAll(async () => {
  await eth.close();
  await goerli.close();
  await avalanche.close();
  await harmony.close();
  await polygon.close();
  await cronos.close();
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

  it('should return 200 when asking for goerli network status', async () => {
    patch(goerli, 'chain', () => {
      return 'goerli';
    });
    patch(goerli, 'rpcUrl', 'http://...');
    patch(goerli, 'chainId', 5);
    patch(goerli, 'getCurrentBlockNumber', () => {
      return 1;
    });

    await request(gatewayApp)
      .get(`/network/status`)
      .query({
        chain: 'ethereum',
        network: 'goerli',
      })
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.chain).toBe('goerli'))
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

  it('should return 200 when asking for polygon network status', async () => {
    patch(polygon, 'chain', () => {
      return 'mumbai';
    });
    patch(polygon, 'rpcUrl', 'http://...');
    patch(polygon, 'chainId', 80001);
    patch(polygon, 'getCurrentBlockNumber', () => {
      return 2;
    });

    await request(gatewayApp)
      .get(`/network/status`)
      .query({
        chain: 'polygon',
        network: 'mumbai',
      })
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.chain).toBe('mumbai'))
      .expect((res) => expect(res.body.chainId).toBeDefined())
      .expect((res) => expect(res.body.rpcUrl).toBeDefined())
      .expect((res) => expect(res.body.currentBlockNumber).toBeDefined());
  });

  it('should return 200 when asking for cronos network status', async () => {
    patch(cronos, 'chain', () => {
      return 'testnet';
    });
    patch(cronos, 'rpcUrl', 'http://...');
    patch(cronos, 'chainId', 338);
    patch(cronos, 'getCurrentBlockNumber', () => {
      return 2;
    });

    await request(gatewayApp)
      .get(`/network/status`)
      .query({
        chain: 'cronos',
        network: 'testnet',
      })
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.chain).toBe('testnet'))
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
  it('should return 200 when retrieving ethereum-kovan tokens, tokenSymbols parameter not provided', async () => {
    await request(gatewayApp)
      .get(`/network/tokens`)
      .query({
        chain: 'ethereum',
        network: 'kovan',
      })
      .expect('Content-Type', /json/)
      .expect(200);
  });

  it('should return 200 when retrieving ethereum-kovan tokens, s parameter provided', async () => {
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

  it('should return 200 when retrieving ethereum-goerli tokens, tokenSymbols parameter not provided', async () => {
    await request(gatewayApp)
      .get(`/network/tokens`)
      .query({
        chain: 'ethereum',
        network: 'goerli',
      })
      .expect('Content-Type', /json/)
      .expect(200);
  });

  it('should return 200 when retrieving ethereum-goerli tokens, tokenSymbols parameter provided', async () => {
    await request(gatewayApp)
      .get(`/network/tokens`)
      .query({
        chain: 'ethereum',
        network: 'goerli',
        tokenSymbols: ['WETH', 'DAI'],
      })
      .expect('Content-Type', /json/)
      .expect(200);
  });

  it('should return 200 when retrieving polygon-mumbai tokens, tokenSymbols parameter not provided', async () => {
    await request(gatewayApp)
      .get(`/network/tokens`)
      .query({
        chain: 'polygon',
        network: 'mumbai',
      })
      .expect('Content-Type', /json/)
      .expect(200);
  });

  it('should return 200 when retrieving polygon-mumbai tokens, tokenSymbols parameter provided', async () => {
    await request(gatewayApp)
      .get(`/network/tokens`)
      .query({
        chain: 'polygon',
        network: 'mumbai',
        tokenSymbols: ['WMATIC', 'WETH'],
      })
      .expect('Content-Type', /json/)
      .expect(200);
  });

  it('should return 200 when retrieving cronos-testnet tokens, tokenSymbols parameter not provided', async () => {
    await request(gatewayApp)
      .get(`/network/tokens`)
      .query({
        chain: 'cronos',
        network: 'testnet',
      })
      .expect('Content-Type', /json/)
      .expect(200);
  });

  it('should return 200 when retrieving cronos-testnet tokens, tokenSymbols parameter provided', async () => {
    await request(gatewayApp)
      .get(`/network/tokens`)
      .query({
        chain: 'cronos',
        network: 'testnet',
        tokenSymbols: ['WCRO', 'WETH'],
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
