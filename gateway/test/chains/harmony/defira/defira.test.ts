jest.useFakeTimers();
import { Defira } from '../../../../src/connectors/defira/defira';
import { patch, unpatch } from '../../../services/patch';
import { UniswapishPriceError } from '../../../../src/services/error-handler';
import { Token, CurrencyAmount, TradeType } from '@uniswap/sdk-core';
import { Trade, Pair, Route } from '@zuzu-cat/defira-sdk';
import { BigNumber } from 'ethers';
import { Harmony } from '../../../../src/chains/harmony/harmony';
import { patchEVMNonceManager } from '../../../evm.nonce.mock';

let harmony: Harmony;
let defira: Defira;

const WONE = new Token(
  3,
  '0x1E120B3b4aF96e7F394ECAF84375b1C661830013',
  18,
  'WONE'
);
const ETH = new Token(
  3,
  '0x7466d7d0C21Fa05F32F5a0Fa27e12bdC06348Ce2',
  18,
  'ETH'
);

beforeAll(async () => {
  harmony = Harmony.getInstance('testnet');
  patchEVMNonceManager(harmony.nonceManager);
  await harmony.init();

  defira = Defira.getInstance('harmony', 'testnet');
  await defira.init();
});

beforeEach(() => {
  patchEVMNonceManager(harmony.nonceManager);
});

afterEach(() => {
  unpatch();
});

afterAll(async () => {
  await harmony.close();
});

const patchFetchData = () => {
  patch(defira, 'fetchPairData', () => {
    return new Pair(
      CurrencyAmount.fromRawAmount(WONE, '2000000000000000000'),
      CurrencyAmount.fromRawAmount(ETH, '1000000000000000000')
    );
  });
};

const patchTrade = (key: string, error?: Error) => {
  patch(Trade, key, () => {
    if (error) return [];
    const WONE_ETH = new Pair(
      CurrencyAmount.fromRawAmount(WONE, '2000000000000000000'),
      CurrencyAmount.fromRawAmount(ETH, '1000000000000000000')
    );
    const ETH_TO_WONE = new Route([WONE_ETH], ETH, WONE);
    return [
      new Trade(
        ETH_TO_WONE,
        CurrencyAmount.fromRawAmount(ETH, '1000000000000000'),
        TradeType.EXACT_INPUT
      ),
    ];
  });
};

describe('verify Defira estimateSellTrade', () => {
  it('Should return an ExpectedTrade when available', async () => {
    patchFetchData();
    patchTrade('bestTradeExactIn');

    const expectedTrade = await defira.estimateSellTrade(
      WONE,
      ETH,
      BigNumber.from(1)
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should throw an error if no pair is available', async () => {
    patchFetchData();
    patchTrade('bestTradeExactIn', new Error('error getting trade'));

    await expect(async () => {
      await defira.estimateSellTrade(WONE, ETH, BigNumber.from(1));
    }).rejects.toThrow(UniswapishPriceError);
  });
});

describe('verify defira estimateBuyTrade', () => {
  it('Should return an ExpectedTrade when available', async () => {
    patchFetchData();
    patchTrade('bestTradeExactOut');

    const expectedTrade = await defira.estimateBuyTrade(
      WONE,
      ETH,
      BigNumber.from(1)
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should return an error if no pair is available', async () => {
    patchFetchData();
    patchTrade('bestTradeExactOut', new Error('error getting trade'));

    await expect(async () => {
      await defira.estimateBuyTrade(WONE, ETH, BigNumber.from(1));
    }).rejects.toThrow(UniswapishPriceError);
  });
});

describe('verify defira Token List', () => {
  it('Should return a token by address', async () => {
    const token = defira.getTokenByAddress(ETH.address);
    expect(token).toBeInstanceOf(Token);
  });
});
