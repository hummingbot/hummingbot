jest.useFakeTimers();
import { Uniswap } from '../../../../src/connectors/uniswap/uniswap';
import { patch, unpatch } from '../../../services/patch';
import { UniswapishPriceError } from '../../../../src/services/error-handler';
import {
  Fetcher,
  Pair,
  Percent,
  Route,
  Token,
  TokenAmount,
  Trade,
  TradeType,
} from '@uniswap/sdk';
import { OverrideConfigs } from '../../../config.util';
import { patchEVMNonceManager } from '../../../evm.nonce.mock';
import { BigNumber } from 'ethers';
import { Ethereum } from '../../../../src/chains/ethereum/ethereum';

const overrideConfigs = new OverrideConfigs();
let ethereum: Ethereum;
let uniswap: Uniswap;

const WETH = new Token(
  3,
  '0xd0A1E359811322d97991E03f863a0C30C2cF029C',
  18,
  'WETH'
);
const DAI = new Token(
  3,
  '0x4f96fe3b7a6cf9725f59d353f723c1bdb64ca6aa',
  18,
  'DAI'
);

beforeAll(async () => {
  await overrideConfigs.init();
  await overrideConfigs.updateConfigs();

  ethereum = Ethereum.getInstance('kovan');
  patchEVMNonceManager(ethereum.nonceManager);
  await ethereum.init();

  uniswap = Uniswap.getInstance('ethereum', 'kovan');
  await uniswap.init();
});

beforeEach(() => {
  patchEVMNonceManager(ethereum.nonceManager);
});

afterEach(() => {
  unpatch();
});

afterAll(async () => {
  await ethereum.close();
  await overrideConfigs.resetConfigs();
});

const patchFetchPairData = () => {
  patch(Fetcher, 'fetchPairData', () => {
    return new Pair(
      new TokenAmount(WETH, '2000000000000000000'),
      new TokenAmount(DAI, '1000000000000000000')
    );
  });
};

const patchTrade = (key: string, error?: Error) => {
  patch(Trade, key, () => {
    if (error) return [];
    const WETH_DAI = new Pair(
      new TokenAmount(WETH, '2000000000000000000'),
      new TokenAmount(DAI, '1000000000000000000')
    );
    const DAI_TO_WETH = new Route([WETH_DAI], DAI);
    return [
      new Trade(
        DAI_TO_WETH,
        new TokenAmount(DAI, '1000000000000000'),
        TradeType.EXACT_INPUT
      ),
    ];
  });
};

describe('verify Uniswap estimateSellTrade', () => {
  it('Should return an ExpectedTrade when available', async () => {
    patchFetchPairData();
    patchTrade('bestTradeExactIn');

    const expectedTrade = await uniswap.estimateSellTrade(
      WETH,
      DAI,
      BigNumber.from(1)
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should throw an error if no pair is available', async () => {
    patchFetchPairData();
    patchTrade('bestTradeExactIn', new Error('error getting trade'));

    await expect(async () => {
      await uniswap.estimateSellTrade(WETH, DAI, BigNumber.from(1));
    }).rejects.toThrow(UniswapishPriceError);
  });
});

describe('verify Uniswap estimateBuyTrade', () => {
  it('Should return an ExpectedTrade when available', async () => {
    patchFetchPairData();
    patchTrade('bestTradeExactOut');

    const expectedTrade = await uniswap.estimateBuyTrade(
      WETH,
      DAI,
      BigNumber.from(1)
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should return an error if no pair is available', async () => {
    patchFetchPairData();
    patchTrade('bestTradeExactOut', new Error('error getting trade'));

    await expect(async () => {
      await uniswap.estimateBuyTrade(WETH, DAI, BigNumber.from(1));
    }).rejects.toThrow(UniswapishPriceError);
  });
});

describe('getAllowedSlippage', () => {
  it('return value of string when not null', () => {
    const allowedSlippage = uniswap.getAllowedSlippage('1/100');
    expect(allowedSlippage).toEqual(new Percent('1', '100'));
  });

  it('return value from config when string is null', () => {
    const allowedSlippage = uniswap.getAllowedSlippage();
    expect(allowedSlippage).toEqual(new Percent('2', '100'));
  });

  it('return value from config when string is malformed', () => {
    const allowedSlippage = uniswap.getAllowedSlippage('yo');
    expect(allowedSlippage).toEqual(new Percent('2', '100'));
  });
});
