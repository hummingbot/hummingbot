jest.useFakeTimers();
import { MadMeerkat } from '../../../../src/connectors/mad_meerkat/mad_meerkat';
import { patch, unpatch } from '../../../services/patch';
import { UniswapishPriceError } from '../../../../src/services/error-handler';
import {
  ChainId,
  Fetcher,
  Pair,
  Percent,
  Route,
  Token,
  TokenAmount,
  Trade,
  TradeType,
} from '@crocswap/sdk';
import { BigNumber } from 'ethers';
import { Cronos } from '../../../../src/chains/cronos/cronos';
import { patchEVMNonceManager } from '../../../evm.nonce.mock';

let cronos: Cronos;
let madMeerkat: MadMeerkat;

const WETH = new Token(
  ChainId.MAINNET,
  '0xd0A1E359811322d97991E03f863a0C30C2cF029C',
  18,
  'WETH'
);
const WAVAX = new Token(
  ChainId.MAINNET,
  '0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7',
  18,
  'WAVAX'
);

beforeAll(async () => {
  cronos = Cronos.getInstance('mainnet');
  patchEVMNonceManager(cronos.nonceManager);
  await cronos.init();
  madMeerkat = MadMeerkat.getInstance('cronos', 'mainnet') as MadMeerkat;
  await madMeerkat.init();
});

beforeEach(() => {
  patchEVMNonceManager(cronos.nonceManager);
});

afterEach(() => {
  unpatch();
});

afterAll(async () => {
  await cronos.close();
});

const patchFetchPairData = () => {
  patch(Fetcher, 'fetchPairData', () => {
    return new Pair(
      new TokenAmount(WETH, '2000000000000000000'),
      new TokenAmount(WAVAX, '1000000000000000000')
    );
  });
};

const patchTrade = (key: string, error?: Error) => {
  patch(Trade, key, () => {
    if (error) return [];
    const WETH_WAVAX = new Pair(
      new TokenAmount(WETH, '2000000000000000000'),
      new TokenAmount(WAVAX, '1000000000000000000')
    );
    const WAVAX_TO_WETH = new Route([WETH_WAVAX], WAVAX);
    return [
      new Trade(
        WAVAX_TO_WETH,
        new TokenAmount(WAVAX, '1000000000000000'),
        TradeType.EXACT_INPUT
      ),
    ];
  });
};

describe('verify MadMeerkat estimateSellTrade', () => {
  it('Should return an ExpectedTrade when available', async () => {
    patchFetchPairData();
    patchTrade('bestTradeExactIn');

    const expectedTrade = await madMeerkat.estimateSellTrade(
      WETH,
      WAVAX,
      BigNumber.from(1)
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should throw an error if no pair is available', async () => {
    patchFetchPairData();
    patchTrade('bestTradeExactIn', new Error('error getting trade'));

    await expect(async () => {
      await madMeerkat.estimateSellTrade(WETH, WAVAX, BigNumber.from(1));
    }).rejects.toThrow(UniswapishPriceError);
  });
});

describe('verify MadMeerkat estimateBuyTrade', () => {
  it('Should return an ExpectedTrade when available', async () => {
    patchFetchPairData();
    patchTrade('bestTradeExactOut');

    const expectedTrade = await madMeerkat.estimateBuyTrade(
      WETH,
      WAVAX,
      BigNumber.from(1)
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should return an error if no pair is available', async () => {
    patchFetchPairData();
    patchTrade('bestTradeExactOut', new Error('error getting trade'));

    await expect(async () => {
      await madMeerkat.estimateBuyTrade(WETH, WAVAX, BigNumber.from(1));
    }).rejects.toThrow(UniswapishPriceError);
  });
});

describe('getAllowedSlippage', () => {
  it('return value of string when not null', () => {
    const allowedSlippage = madMeerkat.getAllowedSlippage('3/100');
    expect(allowedSlippage).toEqual(new Percent('3', '100'));
  });

  it('return value from config when string is null', () => {
    const allowedSlippage = madMeerkat.getAllowedSlippage();
    expect(allowedSlippage).toEqual(new Percent('1', '100'));
  });

  it('return value from config when string is malformed', () => {
    const allowedSlippage = madMeerkat.getAllowedSlippage('yo');
    expect(allowedSlippage).toEqual(new Percent('1', '100'));
  });
});
