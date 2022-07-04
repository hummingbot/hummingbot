jest.useFakeTimers();
import { Sushiswap } from '../../../../src/connectors/sushiswap/sushiswap';
import { patch, unpatch } from '../../../services/patch';
import { UniswapishPriceError as SushiswapishPriceError } from '../../../../src/services/error-handler';
import {
  Token,
  CurrencyAmount,
  Trade,
  Pair,
  TradeType,
  Route,
} from '@sushiswap/sdk';
import { BigNumber } from 'ethers';
import { Ethereum } from '../../../../src/chains/ethereum/ethereum';
import { patchEVMNonceManager } from '../../../evm.nonce.mock';

let ethereum: Ethereum;
let sushiswap: Sushiswap;

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
  ethereum = Ethereum.getInstance('kovan');
  patchEVMNonceManager(ethereum.nonceManager);
  await ethereum.init();

  sushiswap = Sushiswap.getInstance('ethereum', 'kovan');
  await sushiswap.init();
});

beforeEach(() => {
  patchEVMNonceManager(ethereum.nonceManager);
});

afterEach(() => {
  unpatch();
});

afterAll(async () => {
  await ethereum.close();
});

const patchFetchData = () => {
  patch(sushiswap, 'fetchData', () => {
    return new Pair(
      CurrencyAmount.fromRawAmount(WETH, '2000000000000000000'),
      CurrencyAmount.fromRawAmount(DAI, '1000000000000000000')
    );
  });
};
const patchTrade = (key: string, error?: Error) => {
  patch(Trade, key, () => {
    if (error) return [];
    const WETH_DAI = new Pair(
      CurrencyAmount.fromRawAmount(WETH, '2000000000000000000'),
      CurrencyAmount.fromRawAmount(DAI, '1000000000000000000')
    );
    const DAI_TO_WETH = new Route([WETH_DAI], DAI, WETH);
    return [
      new Trade(
        DAI_TO_WETH,
        CurrencyAmount.fromRawAmount(DAI, '1000000000000000'),
        TradeType.EXACT_INPUT
      ),
    ];
  });
};

describe('verify Sushiswap estimateSellTrade', () => {
  it('Should return an ExpectedTrade when available', async () => {
    patchFetchData();
    patchTrade('bestTradeExactIn');

    const expectedTrade = await sushiswap.estimateSellTrade(
      WETH,
      DAI,
      BigNumber.from(1)
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should throw an error if no pair is available', async () => {
    patchFetchData();
    patchTrade('bestTradeExactIn', new Error('error getting trade'));

    await expect(async () => {
      await sushiswap.estimateSellTrade(WETH, DAI, BigNumber.from(1));
    }).rejects.toThrow(SushiswapishPriceError);
  });
});

describe('verify sushiswap estimateBuyTrade', () => {
  it('Should return an ExpectedTrade when available', async () => {
    patchFetchData();
    patchTrade('bestTradeExactOut');

    const expectedTrade = await sushiswap.estimateBuyTrade(
      WETH,
      DAI,
      BigNumber.from(1)
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should return an error if no pair is available', async () => {
    patchFetchData();
    patchTrade('bestTradeExactOut', new Error('error getting trade'));

    await expect(async () => {
      await sushiswap.estimateBuyTrade(WETH, DAI, BigNumber.from(1));
    }).rejects.toThrow(SushiswapishPriceError);
  });
});

describe('verify sushiswap Token List', () => {
  it('Should return a token by address', async () => {
    const token = sushiswap.getTokenByAddress(
      '0x4f96fe3b7a6cf9725f59d353f723c1bdb64ca6aa'
    );
    expect(token).toBeInstanceOf(Token);
  });
});
