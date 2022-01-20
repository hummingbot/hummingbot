jest.useFakeTimers();
import { Pangolin } from '../../../../src/connectors/pangolin/pangolin';
import { patch, unpatch } from '../../../services/patch';
import {
  Fetcher,
  Pair,
  Route,
  Token,
  TokenAmount,
  Trade,
  TradeType,
} from '@pangolindex/sdk';
import { BigNumber } from 'ethers';
import { Avalanche } from '../../../../src/chains/avalanche/avalanche';

let avalanche: Avalanche;
let pangolin: Pangolin;

const FUJISTABLE = new Token(
  43113,
  '0x2058ec2791dD28b6f67DB836ddf87534F4Bbdf22',
  6,
  'FUJISTABLE'
);
const FUJIMOON = new Token(
  43113,
  '0x97132C109c6816525F7f338DCb7435E1412A7668',
  18,
  'FUJIMOON'
);

beforeAll(async () => {
  avalanche = Avalanche.getInstance('fuji');
  await avalanche.init();
  pangolin = Pangolin.getInstance('avalanche', 'fuji');
  await pangolin.init();
});

afterEach(() => {
  unpatch();
});

const patchFetchPairData = () => {
  patch(Fetcher, 'fetchPairData', () => {
    return new Pair(
      new TokenAmount(FUJISTABLE, '2000000000000000000'),
      new TokenAmount(FUJIMOON, '1000000000000000000'),
      3
    );
  });
};

const patchTrade = (key: string, error?: Error) => {
  patch(Trade, key, () => {
    if (error) return [];
    const FUJISTABLE_FUJIMOON = new Pair(
      new TokenAmount(FUJISTABLE, '2000000000000000000'),
      new TokenAmount(FUJIMOON, '1000000000000000000'),
      3
    );
    const DAI_TO_WETH = new Route([FUJISTABLE_FUJIMOON], FUJIMOON);
    return [
      new Trade(
        DAI_TO_WETH,
        new TokenAmount(FUJIMOON, '1000000000000000'),
        TradeType.EXACT_INPUT,
        3
      ),
    ];
  });
};
describe('verify pangolin priceSwapIn', () => {
  it('Should return an ExpectedTrade when available', async () => {
    patchFetchPairData();
    patchTrade('bestTradeExactIn');

    const expectedTrade = await pangolin.priceSwapIn(
      FUJISTABLE,
      FUJIMOON,
      BigNumber.from(1)
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should return an error if no pair is available', async () => {
    patchFetchPairData();
    patchTrade('bestTradeExactIn', new Error('error getting trade'));

    const expectedTrade = await pangolin.priceSwapIn(
      FUJISTABLE,
      FUJIMOON,
      BigNumber.from(1)
    );
    expect(typeof expectedTrade).toBe('string');
  });
});

describe('verify pangolin priceSwapOut', () => {
  it('Should return an ExpectedTrade when available', async () => {
    patchFetchPairData();
    patchTrade('bestTradeExactOut');

    const expectedTrade = await pangolin.priceSwapOut(
      FUJISTABLE,
      FUJIMOON,
      BigNumber.from(1)
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should return an error if no pair is available', async () => {
    patchFetchPairData();
    patchTrade('bestTradeExactOut', new Error('error getting trade'));

    const expectedTrade = await pangolin.priceSwapOut(
      FUJISTABLE,
      FUJIMOON,
      BigNumber.from(1)
    );
    expect(typeof expectedTrade).toBe('string');
  });
});
