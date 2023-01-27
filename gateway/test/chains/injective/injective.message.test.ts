import { MsgBroadcasterLocal } from '../../../src/chains/injective/injective.message';
import { Network } from '@injectivelabs/networks';
import { patch, unpatch } from '../../services/patch';
import {
  MsgBid,
  PrivateKey,
  TxClientBroadcastOptions,
} from '@injectivelabs/sdk-ts';
import { Injective } from '../../../src/chains/injective/injective';
import { patchEVMNonceManager } from '../../evm.nonce.mock';
import { AccountDetails } from '@injectivelabs/sdk-ts/dist/types/auth';
import { TxRaw } from '@injectivelabs/chain-api/cosmos/tx/v1beta1/tx_pb';

const TX_HASH =
  'CC6BF44223B4BD05396F83D55A0ABC0F16CE80836C0E34B08F4558CF72944299'; // noqa: mock
const PRIVATE_KEY = 'somePrivateKey';
const TRANSACTION_RESPONSES_QUEUE: { data: any }[] = [];
let injChain: Injective;
let msgBroadcastLocal: MsgBroadcasterLocal;

beforeAll(async () => {
  injChain = Injective.getInstance('mainnet');
  patchEVMNonceManager(injChain.nonceManager);
  patchCurrentBlockNumber();
  await injChain.init();
  patchPrivateKey();
  msgBroadcastLocal = injChain.broadcaster(PRIVATE_KEY);
});

beforeEach(() => {
  patchEVMNonceManager(injChain.nonceManager);
  patchCurrentBlockNumber();
});

afterEach(() => {
  unpatch();
});

afterAll(async () => {
  await injChain.close();
});

const patchCurrentBlockNumber = (withError: boolean = false) => {
  patch(injChain.chainRestTendermintApi, 'fetchLatestBlock', () => {
    return withError ? {} : { header: { height: 100 } };
  });
};

const patchPrivateKey = (publicKey: string | undefined = undefined) => {
  const privateKeyMock = {
    toPublicKey() {
      return {
        toBase64(): string {
          return publicKey ? publicKey : 'somePublicKey';
        },
      };
    },
    async sign(messageBytes: Buffer): Promise<Uint8Array> {
      return messageBytes;
    },
  };
  patch(PrivateKey, 'fromHex', (_: string) => {
    return privateKeyMock;
  });
};

const patchGetOnChainAccount = () => {
  patch(
    injChain,
    'getOnChainAccount',
    async (injectiveAddress: string): Promise<AccountDetails> => {
      return (async () => {
        return {
          address: injectiveAddress,
          pubKey: { type: 'someType', key: 'someKey' },
          accountNumber: 0,
          sequence: 0,
        };
      })();
    }
  );
};

const patchBroadcastUsingInjective = () => {
  patch(
    msgBroadcastLocal,
    'broadcastUsingInjective',
    async (_: TxRaw, __?: TxClientBroadcastOptions): Promise<{ data: any }> => {
      return TRANSACTION_RESPONSES_QUEUE.shift() as { data: any };
    }
  );
};

const queueTransactionResponse = (txResponse: { data: any }) => {
  TRANSACTION_RESPONSES_QUEUE.push(txResponse);
};

// const patchHttpClient = () => {
//   patch(HttpClient, '')
// }

describe('Test that the getInstance function', () => {
  it('creates a single new instance of the broadcaster per network and private key', () => {
    const firstPrivateKey = 'somePrivateKey';
    const firstInstance = MsgBroadcasterLocal.getInstance({
      network: Network.Mainnet,
      privateKey: firstPrivateKey,
    });

    expect(firstInstance).toBeDefined();

    const secondInstance = MsgBroadcasterLocal.getInstance({
      network: Network.Mainnet,
      privateKey: firstPrivateKey,
    });

    expect(firstInstance === secondInstance).toBeTruthy(); // same reference

    const thirdInstance = MsgBroadcasterLocal.getInstance({
      network: Network.Mainnet,
      privateKey: 'anotherPrivateKey',
    });

    expect(firstInstance === thirdInstance).toBeFalsy();
  });
});

describe('That the broadcast function', () => {
  it('broadcasts a transaction successfully', async () => {
    patchGetOnChainAccount();
    patchBroadcastUsingInjective();
    queueTransactionResponse({
      data: { tx_response: { code: 0, txhash: TX_HASH } },
    });

    const instance = MsgBroadcasterLocal.getInstance({
      network: Network.Mainnet,
      privateKey: PRIVATE_KEY,
    });
    const { txHash } = await instance.broadcast({
      msgs: MsgBid.fromJSON({
        round: 10,
        injectiveAddress: 'someAddress',
        amount: {
          amount: '1',
          denom: 'someDenom',
        },
      }),
      injectiveAddress: 'someAddress',
    });

    expect(txHash).toEqual(TX_HASH);
    expect(TRANSACTION_RESPONSES_QUEUE.length === 0).toBeTruthy();
  });

  it('retries broadcasting after failure due to sequence mismatch', async () => {
    patchGetOnChainAccount();
    patchBroadcastUsingInjective();
    queueTransactionResponse({
      data: {
        tx_response: {
          code: 32,
          raw_log: 'account sequence mismatch, expected 2, got x',
        },
      },
    });
    queueTransactionResponse({
      data: { tx_response: { code: 0, txhash: TX_HASH } },
    });
    const instance = MsgBroadcasterLocal.getInstance({
      network: Network.Mainnet,
      privateKey: PRIVATE_KEY,
    });
    const { txHash } = await instance.broadcast({
      msgs: MsgBid.fromJSON({
        round: 10,
        injectiveAddress: 'someAddress',
        amount: {
          amount: '1',
          denom: 'someDenom',
        },
      }),
      injectiveAddress: 'someAddress',
    });

    expect(txHash).toEqual(TX_HASH);
    expect(TRANSACTION_RESPONSES_QUEUE.length === 0).toBeTruthy();
  });

  it('broadcaster throws error when issues unrelated to sequence arise', async () => {
    patchGetOnChainAccount();
    patchBroadcastUsingInjective();
    queueTransactionResponse({
      data: {
        tx_response: {
          code: 5,
          raw_log:
            '10148642834638inj is smaller than 200000000000000inj: insufficient funds: insufficient funds',
        },
      },
    });
    const instance = MsgBroadcasterLocal.getInstance({
      network: Network.Mainnet,
      privateKey: PRIVATE_KEY,
    });
    await expect(async () => {
      await instance.broadcast({
        msgs: MsgBid.fromJSON({
          round: 10,
          injectiveAddress: 'someAddress',
          amount: {
            amount: '1',
            denom: 'someDenom',
          },
        }),
        injectiveAddress: 'someAddress',
      });
    }).rejects.toThrow(
      '10148642834638inj is smaller than 200000000000000inj: insufficient funds: insufficient funds'
    );
  });
});
