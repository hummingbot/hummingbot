jest.useFakeTimers();
import { UniswapV3 } from '../../../../src/connectors/uniswap/uniswap.v3';
import { patch, unpatch } from '../../../services/patch';
import { UniswapishPriceError } from '../../../../src/services/error-handler';
import { Token } from '@uniswap/sdk-core';
import * as uniV3 from '@uniswap/v3-sdk';
import { BigNumber, Contract, Transaction, Wallet } from 'ethers';
import { Ethereum } from '../../../../src/chains/ethereum/ethereum';
import { UniswapV3Helper } from '../../../../src/connectors/uniswap/uniswap.v3.helper';

let ethereum: Ethereum;
let uniswapV3: UniswapV3;
let uniswapV3Helper: UniswapV3Helper;
let wallet: Wallet;

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
  '0x2F375e94FC336Cdec2Dc0cCB5277FE59CBf1cAe5',
  18,
  'DAI'
);
const TICK_PROVIDER = [
  {
    index: -887270,
    liquidityNet: '118445039955967015140',
    liquidityGross: '118445039955967015140',
  },
  {
    index: 887270,
    liquidityNet: '-118445039955967015140',
    liquidityGross: '118445039955967015140',
  },
];
const TX = {
  type: 2,
  chainId: 42,
  nonce: 115,
  maxPriorityFeePerGas: { toString: () => '106000000000' },
  maxFeePerGas: { toString: () => '106000000000' },
  gasPrice: { toString: () => null },
  gasLimit: { toString: () => '100000' },
  to: '0x4F96Fe3b7A6Cf9725f59d353F723c1bDb64CA6Aa',
  value: { toString: () => '0' },
  data: '0x095ea7b30000000000000000000000007a250d5630b4cf539739df2c5dacb4c659f2488dffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff', // noqa: mock
  accessList: [],
  hash: '0x75f98675a8f64dcf14927ccde9a1d59b67fa09b72cc2642ad055dae4074853d9', // noqa: mock
  v: 0,
  r: '0xbeb9aa40028d79b9fdab108fcef5de635457a05f3a254410414c095b02c64643', // noqa: mock
  s: '0x5a1506fa4b7f8b4f3826d8648f27ebaa9c0ee4bd67f569414b8cd8884c073100', // noqa: mock
  from: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
  confirmations: 0,
};
const POOL_SQRT_RATIO_START = uniV3.encodeSqrtRatioX96(100e6, 100e18);
const POOL_TICK_CURRENT = uniV3.TickMath.getTickAtSqrtRatio(
  POOL_SQRT_RATIO_START
);
const DAI_USDC_POOL = new uniV3.Pool(
  DAI,
  USDC,
  500,
  POOL_SQRT_RATIO_START,
  0,
  POOL_TICK_CURRENT,
  []
);

beforeAll(async () => {
  ethereum = Ethereum.getInstance('kovan');
  await ethereum.init();
  wallet = new Wallet(
    '0000000000000000000000000000000000000000000000000000000000000002', // noqa: mock
    ethereum.provider
  );
  uniswapV3 = UniswapV3.getInstance('ethereum', 'kovan');
  await uniswapV3.init();
  uniswapV3Helper = new UniswapV3Helper('kovan');
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
          '1390012087572052304381352642',
          '6025055903594410671025',
          -80865,
          TICK_PROVIDER
        ),
      ];
    }
    return [
      new uniV3.Pool(
        WETH,
        DAI,
        500,
        '1390012087572052304381352642',
        '6025055903594410671025',
        -80865,
        TICK_PROVIDER
      ),
    ];
  });
};

const patchPoolState = () => {
  patch(uniswapV3, 'getPoolContract', () => {
    return {
      liquidity() {
        return DAI_USDC_POOL.liquidity;
      },
      slot0() {
        return [
          DAI_USDC_POOL.sqrtRatioX96,
          DAI_USDC_POOL.tickCurrent,
          0,
          1,
          1,
          0,
          true,
        ];
      },
      ticks() {
        return ['118445039955967015140', '118445039955967015140'];
      },
    };
  });
};

const patchHelperPoolState = () => {
  patch(uniswapV3Helper, 'getPoolContract', () => {
    return {
      liquidity() {
        return DAI_USDC_POOL.liquidity;
      },
      slot0() {
        return [
          DAI_USDC_POOL.sqrtRatioX96,
          DAI_USDC_POOL.tickCurrent,
          0,
          1,
          1,
          0,
          true,
        ];
      },
      ticks() {
        return ['118445039955967015140', '118445039955967015140'];
      },
    };
  });
};

const patchContract = () => {
  patch(uniswapV3, 'getContract', () => {
    return {
      estimateGas: {
        multicall() {
          return BigNumber.from(5);
        },
      },
      positions() {
        return {
          token0: WETH.address,
          token1: USDC.address,
          fee: 500,
          tickLower: 0,
          tickUpper: 23030,
          liquidity: '6025055903594410671025',
        };
      },
      multicall() {
        return TX;
      },
      collect() {
        return TX;
      },
    };
  });
};

describe('verify UniswapV3 priceSwapIn', () => {
  it('Should return an ExpectedTrade when available', async () => {
    patchFetchPairData();

    const expectedTrade = await uniswapV3.estimateSellTrade(
      WETH,
      DAI,
      BigNumber.from(1)
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should throw an error if no pair is available', async () => {
    patchFetchPairData(true);

    await expect(async () => {
      await uniswapV3.estimateSellTrade(WETH, DAI, BigNumber.from(1));
    }).rejects.toThrow(UniswapishPriceError);
  });
});

describe('verify UniswapV3 priceSwapOut', () => {
  it('Should return an ExpectedTrade when available', async () => {
    patchFetchPairData();

    const expectedTrade = await uniswapV3.estimateBuyTrade(
      WETH,
      DAI,
      BigNumber.from(1)
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should throw an error if no pair is available', async () => {
    patchFetchPairData(true);

    await expect(async () => {
      await uniswapV3.estimateBuyTrade(WETH, DAI, BigNumber.from(1));
    }).rejects.toThrow(UniswapishPriceError);
  });
});

describe('verify UniswapV3 Nft functions', () => {
  it('Should return correct contract addresses', async () => {
    expect(uniswapV3.router).toEqual(
      '0xE592427A0AEce92De3Edee1F18E0157C05861564'
    );
    expect(uniswapV3.nftManager).toEqual(
      '0xC36442b4a4522E871399CD717aBDD847Ab11FE88'
    );
  });

  it('Should return correct contract abi', async () => {
    expect(Array.isArray(uniswapV3.routerAbi)).toEqual(true);
    expect(Array.isArray(uniswapV3.nftAbi)).toEqual(true);
    expect(Array.isArray(uniswapV3.poolAbi)).toEqual(true);
  });

  it('addPositionHelper returns calldata and value', async () => {
    patchPoolState();

    const callData = await uniswapV3.addPositionHelper(
      wallet,
      DAI,
      WETH,
      '10',
      '10',
      500,
      1,
      10
    );
    expect(callData).toHaveProperty('calldata');
    expect(callData).toHaveProperty('value');
  });

  it('reducePositionHelper returns calldata and value', async () => {
    patchPoolState();
    patchContract();

    const callData = await uniswapV3.reducePositionHelper(wallet, 1, 100);
    expect(callData).toHaveProperty('calldata');
    expect(callData).toHaveProperty('value');
  });

  it('basic functions should work', async () => {
    expect(uniswapV3.ready()).toEqual(true);
    expect(uniswapV3.gasLimit).toBeGreaterThan(0);
    expect(
      uniswapV3Helper.getContract('nft', wallet) instanceof Contract
    ).toEqual(true);
    expect(
      uniswapV3Helper.getPoolContract(
        '0x4F96Fe3b7A6Cf9725f59d353F723c1bDb64CA6Aa',
        wallet
      ) instanceof Contract
    ).toEqual(true);
  });

  it('getPairs should return an array', async () => {
    patchHelperPoolState();

    const pairs = await uniswapV3Helper.getPairs(DAI, USDC);
    expect(Array.isArray(pairs)).toEqual(true);
  });

  it('generateOverrides returns overrides correctly', async () => {
    const overrides = uniswapV3.generateOverrides(
      1,
      2,
      3,
      BigNumber.from(4),
      BigNumber.from(5),
      '6'
    );
    expect(overrides.gasLimit).toEqual('1');
    expect(overrides.gasPrice).toBeUndefined();
    expect(overrides.nonce).toEqual(3);
    expect(overrides.maxFeePerGas as BigNumber).toEqual(BigNumber.from(4));
    expect(overrides.maxPriorityFeePerGas as BigNumber).toEqual(
      BigNumber.from(5)
    );
    expect(overrides.value).toEqual('6');
  });

  it('getting fee for reducePosition should work', async () => {
    patchPoolState();
    patchContract();

    const gasFee = await uniswapV3.reducePosition(
      wallet,
      1,
      100,
      true,
      50000,
      10
    );
    expect(parseInt(gasFee.toString())).toEqual(5);
  });

  it('reducePosition should work', async () => {
    patchPoolState();
    patchContract();

    const reduceTx = (await uniswapV3.reducePosition(
      wallet,
      1,
      100,
      false,
      50000,
      10
    )) as Transaction;
    expect(reduceTx.hash).toEqual(
      '0x75f98675a8f64dcf14927ccde9a1d59b67fa09b72cc2642ad055dae4074853d9' // noqa: mock
    );
  });

  it('addPosition should work', async () => {
    patchPoolState();
    patchContract();

    const addTx = await uniswapV3.addPosition(
      wallet,
      DAI,
      WETH,
      '10',
      '10',
      500,
      1,
      10,
      1,
      1,
      1
    );
    expect(addTx.hash).toEqual(
      '0x75f98675a8f64dcf14927ccde9a1d59b67fa09b72cc2642ad055dae4074853d9' // noqa: mock
    );
  });

  it('collectFees should work', async () => {
    patchContract();

    const collectTx = (await uniswapV3.collectFees(
      wallet,
      1,
      false,
      1,
      1
    )) as Transaction;
    expect(collectTx.hash).toEqual(
      '0x75f98675a8f64dcf14927ccde9a1d59b67fa09b72cc2642ad055dae4074853d9' // noqa: mock
    );
  });
});
