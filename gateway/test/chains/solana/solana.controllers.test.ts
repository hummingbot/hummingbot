import { Keypair } from '@solana/web3.js';
import BN from 'bn.js';
import bs58 from 'bs58';
import { Solana } from '../../../src/chains/solana/solana';
import { balances, poll } from '../../../src/chains/solana/solana.controllers';
import {
  SolanaBalanceResponse,
  SolanaPollResponse,
  TransactionResponseStatusCode,
} from '../../../src/chains/solana/solana.requests';
import {
  HttpException,
  LOAD_WALLET_ERROR_CODE,
  LOAD_WALLET_ERROR_MESSAGE,
} from '../../../src/services/error-handler';
import { patch, unpatch } from '../../services/patch';
import { txHash } from '../../services/validators.test';
import * as getTokenListData from './fixtures/getTokenList.json';
import * as getTransactionData from './fixtures/getTransaction.json';
import { privateKey, publicKey } from './solana.validators.test';

let solana: Solana;
beforeAll(async () => {
  solana = await Solana.getInstance('devnet');
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

afterEach(() => {
  unpatch();
});

afterAll(async () => {
  await solana.close();
});

const patchGetKeypair = () => {
  patch(solana, 'getKeypair', (pubkey: string) => {
    return pubkey === publicKey
      ? Keypair.fromSecretKey(bs58.decode(privateKey))
      : null;
  });
};

const CurrentBlockNumber = 112646487;
const patchGetCurrentBlockNumber = () => {
  patch(solana, 'getCurrentBlockNumber', () => CurrentBlockNumber);
};

const patchGetTransaction = () => {
  patch(solana, 'getTransaction', () => getTransactionData);
};

describe('poll', () => {
  it('return transaction data for given signature', async () => {
    patchGetKeypair();
    patchGetCurrentBlockNumber();
    patchGetTransaction();
    const n: SolanaPollResponse = await poll(solana, {
      chain: 'solana',
      network: 'devnet',
      txHash: txHash,
    });
    expect(n.network).toBe(solana.network);
    expect(n.timestamp).toBeNumber();
    expect(n.currentBlock).toBe(CurrentBlockNumber);
    expect(n.txHash).toBe(txHash);
    expect(n.txStatus).toBe(TransactionResponseStatusCode.CONFIRMED);
    expect(n.txData).toStrictEqual(getTransactionData);
  });
});

describe('balances', () => {
  it('fail if wallet not found', async () => {
    const err = 'wallet does not exist';
    patch(solana, 'getKeypair', () => {
      throw new Error(err);
    });

    await expect(
      balances(solana, {
        chain: 'solana',
        network: 'devnet',
        address: publicKey,
        tokenSymbols: ['MBS', 'DAI'],
      })
    ).rejects.toThrow(
      new HttpException(
        500,
        LOAD_WALLET_ERROR_MESSAGE + 'Error: ' + err,
        LOAD_WALLET_ERROR_CODE
      )
    );
  });

  it('return -1 if token account not initialized', async () => {
    patchGetKeypair();
    patch(solana, 'getBalances', () => {
      return {
        MBS: { value: new BN(100), decimals: 3 },
        DAI: undefined,
      };
    });

    expect(
      (
        (await balances(solana, {
          chain: 'solana',
          network: 'devnet',
          address: publicKey,
          tokenSymbols: ['MBS', 'DAI'],
        })) as SolanaBalanceResponse
      ).balances
    ).toStrictEqual({ MBS: '0.100', DAI: '-1' });
  });
});
