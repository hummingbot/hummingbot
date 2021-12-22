import request from 'supertest';
import { patch, unpatch } from '../../services/patch';
import { app } from '../../../src/app';
import { Solana } from '../../../src/chains/solana/solana';
import { privateKey, publicKey } from './solana.validators.test';
import { tokenSymbols, txHash } from '../../services/validators.test';
import { TransactionResponseStatusCode } from '../../../src/chains/solana/solana.requests';
import * as getTransactionData from './fixtures/getTransaction.json';
import * as getTokenAccountData from './fixtures/getTokenAccount.json';
import * as getTokenListData from './fixtures/getTokenList.json';

let solana: Solana;
beforeAll(async () => {
  solana = Solana.getInstance();
  solana.getTokenList = jest
    .fn()
    .mockReturnValue([
      getTokenListData[0],
      getTokenListData[1],
      getTokenListData[2],
      getTokenListData[3],
    ]);
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

const patchGetTokenAccount = () => {
  patch(solana, 'getTokenAccount', () => getTokenAccountData);
};

const patchGetSplBalance = () => {
  patch(solana, 'getSplBalance', () => {
    return { value: 3, decimals: 3 };
  });
};

describe('GET /solana/token', () => {
  it('should get accountAddress = undefined when Token account not found', async () => {
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
      .expect((res) =>
        expect(res.body.mintAddress).toBe(getTokenListData[0].address)
      )
      .expect((res) => expect(res.body.accountAddress).toBeUndefined())
      .expect((res) => expect(res.body.amount).toBe('0.003'));
  });

  it('should get amount = undefined when Token account not initialized', async () => {
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
      .expect((res) =>
        expect(res.body.mintAddress).toBe(getTokenListData[0].address)
      )
      .expect((res) =>
        expect(res.body.accountAddress).toBe(getTokenAccountData.owner)
      )
      .expect((res) => expect(res.body.amount).toBeUndefined());
  });

  it('should return 200', async () => {
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
      .expect((res) =>
        expect(res.body.mintAddress).toBe(getTokenListData[0].address)
      )
      .expect((res) =>
        expect(res.body.accountAddress).toBe(getTokenAccountData.owner)
      )
      .expect((res) => expect(res.body.amount).toBe('0.003'));
  });

  it('should return 501 when token not found', async () => {
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
  patch(solana, 'getOrCreateAssociatedTokenAccount', () => getTokenAccountData);
};

describe('POST /solana/token', () => {
  it('should get accountAddress = undefined when Token account not found', async () => {
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
      .expect((res) =>
        expect(res.body.mintAddress).toBe(getTokenListData[0].address)
      )
      .expect((res) => expect(res.body.accountAddress).toBeUndefined())
      .expect((res) => expect(res.body.amount).toBe('0.003'));
  });

  it('should get amount = undefined when Token account not initialized', async () => {
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
      .expect((res) =>
        expect(res.body.mintAddress).toBe(getTokenListData[0].address)
      )
      .expect((res) =>
        expect(res.body.accountAddress).toBe(getTokenAccountData.owner)
      )
      .expect((res) => expect(res.body.amount).toBeUndefined());
  });

  it('should return 200', async () => {
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
      .expect((res) =>
        expect(res.body.mintAddress).toBe(getTokenListData[0].address)
      )
      .expect((res) =>
        expect(res.body.accountAddress).toBe(getTokenAccountData.owner)
      )
      .expect((res) => expect(res.body.amount).toBe('0.003'));
  });

  it('should return 404 when parameters are invalid', async () => {
    await request(app).post(`/solana/token`).send({}).expect(404);
  });
});

const CurrentBlockNumber = 112646487;
const patchGetCurrentBlockNumber = () => {
  patch(solana, 'getCurrentBlockNumber', () => CurrentBlockNumber);
};

const patchGetTransaction = () => {
  patch(solana, 'getTransaction', () => getTransactionData);
};

describe('POST /solana/poll', () => {
  it('should return 200', async () => {
    patchGetCurrentBlockNumber();
    patchGetTransaction();

    await request(app)
      .post(`/solana/poll`)
      .send({ txHash })
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.network).toBe(solana.cluster))
      .expect((res) => expect(res.body.timestamp).toBeNumber())
      .expect((res) => expect(res.body.currentBlock).toBe(CurrentBlockNumber))
      .expect((res) => expect(res.body.txHash).toBe(txHash))
      .expect((res) =>
        expect(res.body.txStatus).toBe(TransactionResponseStatusCode.CONFIRMED)
      )
      .expect((res) =>
        expect(res.body.txData).toStrictEqual(getTransactionData)
      );
  });

  it('should return 404 when parameters are invalid', async () => {
    await request(app).post(`/solana/poll`).send({}).expect(404);
  });
});
