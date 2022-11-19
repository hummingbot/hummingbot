import { Near } from '../../../src/chains/near/near';
import { TokenInfo } from '../../../src/chains/near/near.base';
import {
  balances,
  cancel,
  getTokenSymbolsToTokens,
  poll,
} from '../../../src/chains/near/near.controllers';
import { PollResponse } from '../../../src/chains/near/near.requests';
import { Nearish } from '../../../src/services/common-interfaces';
import {
  HttpException,
  LOAD_WALLET_ERROR_CODE,
  LOAD_WALLET_ERROR_MESSAGE,
} from '../../../src/services/error-handler';
import { patch, unpatch } from '../../services/patch';
import * as getTokenListData from './fixtures/getTokenList.json';
import * as getTransactionData from './fixtures/getTransaction.json';
import { publicKey } from './near.validators.test';

let near: Nearish;
const txHash = 'JCVEmLB2EQUR5hijgJkLLKjW5aGxdcdAndTQZBZ85Fm8';
const zeroAddress =
  '0000000000000000000000000000000000000000000000000000000000000000'; // noqa: mock

beforeAll(async () => {
  near = Near.getInstance('testnet');
  near.getTokenList = jest.fn().mockReturnValue(getTokenListData);
  await near.init();
});

afterEach(() => {
  unpatch();
});

afterAll(async () => {
  await near.close();
});

const CurrentBlockNumber = 112646487;
const patchGetCurrentBlockNumber = () => {
  patch(near, 'getCurrentBlockNumber', () => CurrentBlockNumber);
};

const patchGetTransaction = () => {
  patch(near, 'getTransaction', () => getTransactionData);
};

describe('poll', () => {
  it('return transaction data for given signature', async () => {
    patchGetCurrentBlockNumber();
    patchGetTransaction();
    const n: PollResponse = await poll(near, publicKey, txHash);
    expect(n.network).toBe(near.network);
    expect(n.timestamp).toBeNumber();
    expect(n.currentBlock).toBe(CurrentBlockNumber);
    expect(n.txHash).toBe(txHash);
    expect(n.txStatus).toBe(1);
  });
});

describe('balances', () => {
  it('fail if wallet not found', async () => {
    const err = 'wallet does not exist';
    patch(near, 'getWallet', () => {
      throw new Error(err);
    });

    await expect(
      balances(near, {
        chain: 'near',
        network: 'testnet',
        address: publicKey,
        tokenSymbols: ['ETHH', 'NEAR'],
      })
    ).rejects.toThrow(
      new HttpException(
        500,
        LOAD_WALLET_ERROR_MESSAGE + 'Error: ' + err,
        LOAD_WALLET_ERROR_CODE
      )
    );
  });
});

describe('cancel', () => {
  it('fail if wallet not found', async () => {
    const err = 'wallet does not exist';
    patch(near, 'getWallet', () => {
      throw new Error(err);
    });

    await expect(
      cancel(near, {
        chain: 'near',
        network: 'testnet',
        nonce: 123,
        address: zeroAddress,
      })
    ).rejects.toThrow(
      new HttpException(
        500,
        LOAD_WALLET_ERROR_MESSAGE + 'Error: ' + err,
        LOAD_WALLET_ERROR_CODE
      )
    );
  });
});

const eth: TokenInfo = {
  chainId: 0,
  name: 'ETH',
  symbol: 'ETH',
  address: 'eth.near',
  decimals: 18,
};
describe('getTokenSymbolsToTokens', () => {
  it('return tokens for strings', () => {
    patch(near, 'getTokenBySymbol', () => {
      return eth;
    });
    expect(getTokenSymbolsToTokens(near, ['ETH'])).toEqual({ ETH: eth });
  });
});
