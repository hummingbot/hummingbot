jest.useFakeTimers();
import { UniswapV3 } from '../../../../src/connectors/uniswap/uniswap.v3';
import { patch, unpatch } from '../../../services/patch';
import { Token } from '@uniswap/sdk-core';
import * as uniV3 from '@uniswap/v3-sdk';
import { BigNumber } from 'ethers';
import { Ethereum } from '../../../../src/chains/ethereum/ethereum';

let ethereum: Ethereum;
let uniswapV3: UniswapV3;

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
const USDC = new Token(
  3,
  '0x4f22fe3b7a6cf9725f59d353f723c1bdb64ca6aa',
  18,
  'DAI'
);
const tickProvider = [
  {
    index: -887270,
    liquidityNet: 118445039955967015140,
    liquidityGross: 118445039955967015140,
  },
  {
    index: 887270,
    liquidityNet: -118445039955967015140,
    liquidityGross: 118445039955967015140,
  },
];

beforeAll(async () => {
  ethereum = Ethereum.getInstance('kovan');
  await ethereum.init();
  uniswapV3 = UniswapV3.getInstance('ethereum', 'kovan');
  await uniswapV3.init();
});

afterEach(() => {
  unpatch();
});

const patchFetchPairData = (noPath?: boolean) => {
  patch(uniswapV3, 'getPairs', () => {
    if (noPath) {
      return [
        new uniV3.Pool(
          WETH,
          USDC,
          500,
          1390012087572052304381352642,
          6025055903594410671025,
          -80865,
          tickProvider
        ),
      ];
    }
    return [
      new uniV3.Pool(
        WETH,
        DAI,
        500,
        1390012087572052304381352642,
        6025055903594410671025,
        -80865,
        tickProvider
      ),
    ];
  });
};

describe('verify UniswapV3 priceSwapIn', () => {
  it('Should return an ExpectedTrade when available', async () => {
    patchFetchPairData();

    const expectedTrade = await uniswapV3.priceSwapIn(
      WETH,
      DAI,
      BigNumber.from(1)
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should return an error if no pair is available', async () => {
    patchFetchPairData(true);

    const expectedTrade = await uniswapV3.priceSwapIn(
      WETH,
      DAI,
      BigNumber.from(1)
    );
    expect(typeof expectedTrade).toBe('string');
  });
});

describe('verify UniswapV3 priceSwapOut', () => {
  it('Should return an ExpectedTrade when available', async () => {
    patchFetchPairData();

    const expectedTrade = await uniswapV3.priceSwapOut(
      WETH,
      DAI,
      BigNumber.from(1)
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should return an error if no pair is available', async () => {
    patchFetchPairData(true);

    const expectedTrade = await uniswapV3.priceSwapOut(
      WETH,
      DAI,
      BigNumber.from(1)
    );
    expect(typeof expectedTrade).toBe('string');
  });
});
