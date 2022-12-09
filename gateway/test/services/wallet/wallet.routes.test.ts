import request from 'supertest';
import { gatewayApp } from '../../../src/app';
import { patch, unpatch } from '../patch';
import { Ethereum } from '../../../src/chains/ethereum/ethereum';
import { Avalanche } from '../../../src/chains/avalanche/avalanche';
import { Harmony } from '../../../src/chains/harmony/harmony';
import { ConfigManagerCertPassphrase } from '../../../src/services/config-manager-cert-passphrase';
import { GetWalletResponse } from '../../../src/services/wallet/wallet.requests';
let avalanche: Avalanche;
let eth: Ethereum;
let harmony: Harmony;

beforeAll(async () => {
  patch(ConfigManagerCertPassphrase, 'readPassphrase', () => 'a');

  avalanche = Avalanche.getInstance('fuji');
  eth = Ethereum.getInstance('kovan');
  harmony = Harmony.getInstance('testnet');
});

beforeEach(() =>
  patch(ConfigManagerCertPassphrase, 'readPassphrase', () => 'a')
);

afterAll(async () => {
  await avalanche.close();
  await eth.close();
  await harmony.close();
});

afterEach(() => unpatch());

const twoAddress = '0x2b5ad5c4795c026514f8317c7a215e218dccd6cf';

const twoPrivateKey =
  '0000000000000000000000000000000000000000000000000000000000000002'; // noqa: mock

// encoding of twoPrivateKey with the password 'a'
const encodedPrivateKey = {
  address: '2b5ad5c4795c026514f8317c7a215e218dccd6cf',
  id: '116e3405-ea6c-40ba-93c0-6a835ad2ea99',
  version: 3,
  Crypto: {
    cipher: 'aes-128-ctr',
    cipherparams: { iv: 'dccf7a5f7d66bc6a61cf4fda422dcd55' },
    ciphertext:
      'ce561ad92c6a507a9399f51d64951b763f01b4956f15fd298ceb7a1174d0394a', // noqa: mock
    kdf: 'scrypt',
    kdfparams: {
      salt: 'a88d99c6d01150af02861ebb1ace3b633a33b2a20561fe188a0c260a84d1ba99', // noqa: mock
      n: 131072,
      dklen: 32,
      p: 1,
      r: 8,
    },
    mac: '684b0111ed08611ad993c76b4524d5dcda18b26cb930251983c36f40160eba8f', // noqa: mock
  },
};

describe('POST /wallet/add', () => {
  it('return 200 for well formed ethereum request', async () => {
    patch(eth, 'getWalletFromPrivateKey', () => {
      return {
        address: twoAddress,
      };
    });

    patch(eth, 'encrypt', () => {
      return JSON.stringify(encodedPrivateKey);
    });

    await request(gatewayApp)
      .post(`/wallet/add`)
      .send({
        privateKey: twoPrivateKey,
        chain: 'ethereum',
        network: 'kovan',
      })
      .expect('Content-Type', /json/)
      .expect(200);
  });

  it('return 200 for well formed avalanche request', async () => {
    patch(avalanche, 'getWalletFromPrivateKey', () => {
      return {
        address: twoAddress,
      };
    });

    patch(avalanche, 'encrypt', () => {
      return JSON.stringify(encodedPrivateKey);
    });

    await request(gatewayApp)
      .post(`/wallet/add`)
      .send({
        privateKey: twoPrivateKey,
        chain: 'avalanche',
        network: 'fuji',
      })

      .expect('Content-Type', /json/)
      .expect(200);
  });

  it('return 200 for well formed harmony request', async () => {
    patch(harmony, 'getWalletFromPrivateKey', () => {
      return {
        address: twoAddress,
      };
    });

    patch(harmony, 'encrypt', () => {
      return JSON.stringify(encodedPrivateKey);
    });

    await request(gatewayApp)
      .post(`/wallet/add`)
      .send({
        privateKey: twoPrivateKey,
        chain: 'harmony',
        network: 'testnet',
      })

      .expect('Content-Type', /json/)
      .expect(200);
  });

  it('return 404 for ill-formed avalanche request', async () => {
    patch(avalanche, 'getWalletFromPrivateKey', () => {
      return {
        address: twoAddress,
      };
    });

    patch(avalanche, 'encrypt', () => {
      return JSON.stringify(encodedPrivateKey);
    });

    await request(gatewayApp)
      .post(`/wallet/add`)
      .send({})
      .expect('Content-Type', /json/)
      .expect(404);
  });

  it('return 404 for ill-formed harmony request', async () => {
    patch(harmony, 'getWalletFromPrivateKey', () => {
      return {
        address: twoAddress,
      };
    });

    patch(harmony, 'encrypt', () => {
      return JSON.stringify(encodedPrivateKey);
    });

    await request(gatewayApp)
      .post(`/wallet/add`)
      .send({})
      .expect('Content-Type', /json/)
      .expect(404);
  });
});

describe('DELETE /wallet/remove', () => {
  it('return 200 for well formed ethereum request', async () => {
    patch(eth, 'getWalletFromPrivateKey', () => {
      return {
        address: twoAddress,
      };
    });

    patch(eth, 'encrypt', () => {
      return JSON.stringify(encodedPrivateKey);
    });

    await request(gatewayApp)
      .post(`/wallet/add`)
      .send({
        privateKey: twoPrivateKey,
        chain: 'ethereum',
        network: 'kovan',
      })

      .expect('Content-Type', /json/)
      .expect(200);

    await request(gatewayApp)
      .delete(`/wallet/remove`)
      .send({
        address: twoAddress,
        chain: 'ethereum',
      })

      .expect('Content-Type', /json/)
      .expect(200);
  });

  it('return 200 for well formed harmony request', async () => {
    patch(harmony, 'getWalletFromPrivateKey', () => {
      return {
        address: twoAddress,
      };
    });

    patch(harmony, 'encrypt', () => {
      return JSON.stringify(encodedPrivateKey);
    });

    await request(gatewayApp)
      .post(`/wallet/add`)
      .send({
        privateKey: twoPrivateKey,
        chain: 'harmony',
        network: 'testnet',
      })

      .expect('Content-Type', /json/)
      .expect(200);

    await request(gatewayApp)
      .delete(`/wallet/remove`)
      .send({
        address: twoAddress,
        chain: 'harmony',
      })

      .expect('Content-Type', /json/)
      .expect(200);
  });

  it('return 404 for ill-formed request', async () => {
    await request(gatewayApp).delete(`/wallet/delete`).send({}).expect(404);
  });
});

describe('GET /wallet', () => {
  it('return 200 for well formed ethereum request', async () => {
    patch(eth, 'getWalletFromPrivateKey', () => {
      return {
        address: twoAddress,
      };
    });

    patch(eth, 'encrypt', () => {
      return JSON.stringify(encodedPrivateKey);
    });

    await request(gatewayApp)
      .post(`/wallet/add`)
      .send({
        privateKey: twoPrivateKey,
        chain: 'ethereum',
        network: 'kovan',
      })
      .expect('Content-Type', /json/)
      .expect(200);

    await request(gatewayApp)
      .get(`/wallet`)
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => {
        const wallets: GetWalletResponse[] = res.body;
        const addresses: string[][] = wallets
          .filter((wallet) => wallet.chain === 'ethereum')
          .map((wallet) => wallet.walletAddresses);

        expect(addresses[0]).toContain(twoAddress);
      });
  });

  it('return 200 for well formed harmony request', async () => {
    patch(harmony, 'getWalletFromPrivateKey', () => {
      return {
        address: twoAddress,
      };
    });

    patch(harmony, 'encrypt', () => {
      return JSON.stringify(encodedPrivateKey);
    });

    await request(gatewayApp)
      .post(`/wallet/add`)
      .send({
        privateKey: twoPrivateKey,
        chain: 'harmony',
        network: 'testnet',
      })
      .expect('Content-Type', /json/)
      .expect(200);

    await request(gatewayApp)
      .get(`/wallet`)
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => {
        const wallets: GetWalletResponse[] = res.body;
        const addresses: string[][] = wallets
          .filter((wallet) => wallet.chain === 'harmony')
          .map((wallet) => wallet.walletAddresses);

        expect(addresses[0]).toContain(twoAddress);
      });
  });
});
