import request from 'supertest';
import { patch, unpatch } from '../../services/patch';
import { app } from '../../../src/app';
import { Solana } from '../../../src/chains/solana/solana';
import { privateKey, publicKey } from './solana.validators.test';
import { tokenSymbols, txHash } from '../../services/validators.test';
import { TransactionResponseStatusCode } from '../../../src/chains/solana/solana.requests';
import * as transactionSuccessful from './fixtures/transaction-successful.json';

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

const tokenAccount = {
  owner: publicKey,
};
const patchGetTokenAccount = () => {
  patch(solana, 'getTokenAccount', () => {
    return tokenAccount;
  });
};

const patchGetTokenForSymbol = () => {
  patch(solana, 'getTokenForSymbol', () => {
    return {
      address: publicKey,
    };
  });
};

const patchGetSplBalance = () => {
  patch(solana, 'getSplBalance', () => {
    return { value: 3, decimals: 3 };
  });
};

describe('GET /solana/token', () => {
  it('should get accountAddress = undefined when Token account not found', async () => {
    patchGetTokenForSymbol();
    patch(solana, 'getTokenAccount', () => {
      return null;
    });
    patchGetSplBalance();

    await request(app)
      .get(`/solana/token`)
      .send({ token: tokenSymbols[0], publicKey })
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.network).toBe(solana.cluster))
      .expect((res) => expect(res.body.timestamp).toBeNumber())
      .expect((res) => expect(res.body.token).toBe(tokenSymbols[0]))
      .expect((res) => expect(res.body.mintAddress).toBe(publicKey))
      .expect((res) => expect(res.body.accountAddress).toBeUndefined())
      .expect((res) => expect(res.body.amount).toBe('0.003'));
  });

  it('should get amount = undefined when Token account not initialized', async () => {
    patchGetTokenForSymbol();
    patchGetTokenAccount();
    patch(solana, 'getSplBalance', () => {
      throw new Error(`Token account not initialized`);
    });

    await request(app)
      .get(`/solana/token`)
      .send({ token: tokenSymbols[0], publicKey })
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.network).toBe(solana.cluster))
      .expect((res) => expect(res.body.timestamp).toBeNumber())
      .expect((res) => expect(res.body.token).toBe(tokenSymbols[0]))
      .expect((res) => expect(res.body.mintAddress).toBe(publicKey))
      .expect((res) => expect(res.body.accountAddress).toBe(publicKey))
      .expect((res) => expect(res.body.amount).toBeUndefined());
  });

  it('should return 200', async () => {
    patchGetTokenForSymbol();
    patchGetTokenAccount();
    patchGetSplBalance();

    await request(app)
      .get(`/solana/token`)
      .send({ token: tokenSymbols[0], publicKey })
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.network).toBe(solana.cluster))
      .expect((res) => expect(res.body.timestamp).toBeNumber())
      .expect((res) => expect(res.body.token).toBe(tokenSymbols[0]))
      .expect((res) => expect(res.body.mintAddress).toBe(publicKey))
      .expect((res) => expect(res.body.accountAddress).toBe(publicKey))
      .expect((res) => expect(res.body.amount).toBe('0.003'));
  });

  it('should return 501 when token not found', async () => {
    patch(solana, 'getTokenForSymbol', () => null);

    await request(app)
      .get(`/solana/token`)
      .send({ token: 'not found', publicKey })
      .expect(501);
  });
  it('should return 404 when parameters are invalid', async () => {
    await request(app).get(`/solana/token`).send({}).expect(404);
  });
});

const patchGetOrCreateAssociatedTokenAccount = () => {
  patch(solana, 'getOrCreateAssociatedTokenAccount', () => {
    return tokenAccount;
  });
};

describe('POST /solana/token', () => {
  it('should get accountAddress = undefined when Token account not found', async () => {
    patchGetTokenForSymbol();
    patch(solana, 'getOrCreateAssociatedTokenAccount', () => {
      return null;
    });
    patchGetSplBalance();

    await request(app)
      .post(`/solana/token`)
      .send({ token: tokenSymbols[0], privateKey })
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.network).toBe(solana.cluster))
      .expect((res) => expect(res.body.timestamp).toBeNumber())
      .expect((res) => expect(res.body.token).toBe(tokenSymbols[0]))
      .expect((res) => expect(res.body.mintAddress).toBe(publicKey))
      .expect((res) => expect(res.body.accountAddress).toBeUndefined())
      .expect((res) => expect(res.body.amount).toBe('0.003'));
  });

  it('should get amount = undefined when Token account not initialized', async () => {
    patchGetTokenForSymbol();
    patchGetOrCreateAssociatedTokenAccount();
    patch(solana, 'getSplBalance', () => {
      throw new Error(`Token account not initialized`);
    });

    await request(app)
      .post(`/solana/token`)
      .send({ token: tokenSymbols[0], privateKey })
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.network).toBe(solana.cluster))
      .expect((res) => expect(res.body.timestamp).toBeNumber())
      .expect((res) => expect(res.body.token).toBe(tokenSymbols[0]))
      .expect((res) => expect(res.body.mintAddress).toBe(publicKey))
      .expect((res) => expect(res.body.accountAddress).toBe(publicKey))
      .expect((res) => expect(res.body.amount).toBeUndefined());
  });

  it('should return 200', async () => {
    patchGetTokenForSymbol();
    patchGetOrCreateAssociatedTokenAccount();
    patchGetSplBalance();

    await request(app)
      .post(`/solana/token`)
      .send({ token: tokenSymbols[0], privateKey })
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.network).toBe(solana.cluster))
      .expect((res) => expect(res.body.timestamp).toBeNumber())
      .expect((res) => expect(res.body.token).toBe(tokenSymbols[0]))
      .expect((res) => expect(res.body.mintAddress).toBe(publicKey))
      .expect((res) => expect(res.body.accountAddress).toBe(publicKey))
      .expect((res) => expect(res.body.amount).toBe('0.003'));
  });

  it('should return 404 when parameters are invalid', async () => {
    await request(app).post(`/solana/token`).send({}).expect(404);
  });
});

const patchGetCurrentBlockNumber = () => {
  patch(solana, 'getCurrentBlockNumber', () => 112646487);
};

const patchGetTransaction = () => {
  patch(solana, 'getTransaction', () => transactionSuccessful);
};

const patchGetTransactionStatusCode = () => {
  patch(
    solana,
    'getTransactionStatusCode',
    () => TransactionResponseStatusCode.CONFIRMED
  );
};

describe('POST /solana/poll', () => {
  it('should return 200', async () => {
    patchGetCurrentBlockNumber();
    patchGetTransaction();
    patchGetTransactionStatusCode();

    await request(app)
      .post(`/solana/poll`)
      .send({ txHash })
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.network).toBe(solana.cluster))
      .expect((res) => expect(res.body.timestamp).toBeNumber())
      .expect((res) => expect(res.body.currentBlock).toBe(112646487))
      .expect((res) => expect(res.body.txHash).toBe(txHash))
      .expect((res) =>
        expect(res.body.txStatus).toBe(TransactionResponseStatusCode.CONFIRMED)
      )
      .expect((res) =>
        expect(res.body.txData).toStrictEqual(transactionSuccessful)
      );
  });

  it('should return 404 when parameters are invalid', async () => {
    await request(app).post(`/solana/poll`).send({}).expect(404);
  });
});
