jest.useFakeTimers();
import { Quickswap } from '../../../../src/connectors/quickswap/quickswap';
import { patch, unpatch } from '../../../services/patch';
import { UniswapishPriceError } from '../../../../src/services/error-handler';
import {
  Fetcher,
  Percent,
  Token,
  TokenAmount,
  Trade,
  Pair,
  TradeType,
  Route,
} from 'quickswap-sdk';
import { BigNumber } from 'ethers';
import { Polygon } from '../../../../src/chains/polygon/polygon';
import { patchEVMNonceManager } from '../../../evm.nonce.mock';

let polygon: Polygon;
let quickswap: Quickswap;

const WMATIC = new Token(
  80001,
  '0x9c3c9283d3e44854697cd22d3faa240cfb032889',
  18,
  'WMATIC'
);
const WETH = new Token(
  80001,
  '0xa6fa4fb5f76172d178d61b04b0ecd319c5d1c0aa',
  18,
  'WETH'
);

beforeAll(async () => {
  polygon = Polygon.getInstance('mumbai');
  patchEVMNonceManager(polygon.nonceManager);
  await polygon.init();

  quickswap = Quickswap.getInstance('polygon', 'mumbai');
  await quickswap.init();
});

beforeEach(() => {
  patchEVMNonceManager(polygon.nonceManager);
});

afterEach(() => {
  unpatch();
});

afterAll(async () => {
  await polygon.close();
});

const patchFetchPairData = () => {
  patch(Fetcher, 'fetchPairData', () => {
    return new Pair(
      new TokenAmount(WMATIC, '2000000000000000000'),
      new TokenAmount(WETH, '1000000000000000000')
    );
  });
};

const patchTrade = (key: string, error?: Error) => {
  patch(Trade, key, () => {
    if (error) return [];
    const WMATIC_WETH = new Pair(
      new TokenAmount(WMATIC, '2000000000000000000'),
      new TokenAmount(WETH, '1000000000000000000')
    );
    const WETH_TO_WMATIC = new Route([WMATIC_WETH], WETH, WMATIC);
    return [
      new Trade(
        WETH_TO_WMATIC,
        new TokenAmount(WETH, '1000000000000000'),
        TradeType.EXACT_INPUT
      ),
    ];
  });
};

describe('verify Quickswap estimateSellTrade', () => {
  it('Should return an ExpectedTrade when available', async () => {
    patchFetchPairData();
    patchTrade('bestTradeExactIn');

    const expectedTrade = await quickswap.estimateSellTrade(
      WMATIC,
      WETH,
      BigNumber.from(1)
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should throw an error if no pair is available', async () => {
    patchFetchPairData();
    patchTrade('bestTradeExactIn', new Error('error getting trade'));

    await expect(async () => {
      await quickswap.estimateSellTrade(WMATIC, WETH, BigNumber.from(1));
    }).rejects.toThrow(UniswapishPriceError);
  });
});

describe('verify Quickswap estimateBuyTrade', () => {
  it('Should return an ExpectedTrade when available', async () => {
    patchFetchPairData();
    patchTrade('bestTradeExactOut');

    const expectedTrade = await quickswap.estimateBuyTrade(
      WMATIC,
      WETH,
      BigNumber.from(1)
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should return an error if no pair is available', async () => {
    patchFetchPairData();
    patchTrade('bestTradeExactOut', new Error('error getting trade'));

    await expect(async () => {
      await quickswap.estimateBuyTrade(WMATIC, WETH, BigNumber.from(1));
    }).rejects.toThrow(UniswapishPriceError);
  });
});

describe('getAllowedSlippage', () => {
  it('return value of string when not null', () => {
    const allowedSlippage = quickswap.getAllowedSlippage('3/100');
    expect(allowedSlippage).toEqual(new Percent('3', '100'));
  });

  it('return value from config when string is null', () => {
    const allowedSlippage = quickswap.getAllowedSlippage();
    expect(allowedSlippage).toEqual(new Percent('1', '100'));
  });

  it('return value from config when string is malformed', () => {
    const allowedSlippage = quickswap.getAllowedSlippage('yo');
    expect(allowedSlippage).toEqual(new Percent('1', '100'));
  });
});
