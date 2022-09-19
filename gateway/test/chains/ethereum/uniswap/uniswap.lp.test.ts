jest.useFakeTimers();
import { Token } from '@uniswap/sdk-core';
import * as uniV3 from '@uniswap/v3-sdk';
import { BigNumber, Transaction, Wallet } from 'ethers';
import { Ethereum } from '../../../../src/chains/ethereum/ethereum';
import { UniswapLP } from '../../../../src/connectors/uniswap/uniswap.lp';
import { patch, unpatch } from '../../../services/patch';
import { patchEVMNonceManager } from '../../../evm.nonce.mock';
let ethereum: Ethereum;
let uniswapLP: UniswapLP;
let wallet: Wallet;

const WETH = new Token(
  42,
  '0xd0A1E359811322d97991E03f863a0C30C2cF029C',
  18,
  'WETH'
);

const DAI = new Token(
  42,
  '0x4f96fe3b7a6cf9725f59d353f723c1bdb64ca6aa',
  18,
  'DAI'
);

const USDC = new Token(
  42,
  '0x2F375e94FC336Cdec2Dc0cCB5277FE59CBf1cAe5',
  18,
  'DAI'
);

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
  patchEVMNonceManager(ethereum.nonceManager);
  await ethereum.init();

  wallet = new Wallet(
    '0000000000000000000000000000000000000000000000000000000000000002', // noqa: mock
    ethereum.provider
  );
  uniswapLP = UniswapLP.getInstance('ethereum', 'kovan');
  await uniswapLP.init();
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

const patchPoolState = () => {
  patch(uniswapLP, 'getPoolContract', () => {
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
        return ['-118445039955967015140', '118445039955967015140'];
      },
    };
  });
};

const patchAlphaRouter = () => {
  patch(uniswapLP.alphaRouter, 'routeToRatio', () => {
    return { status: 3 };
  });
};

const patchContract = () => {
  patch(uniswapLP, 'getContract', () => {
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

const patchWallet = () => {
  patch(wallet, 'sendTransaction', () => {
    return TX;
  });
};

describe('verify UniswapLP Nft functions', () => {
  it('Should return correct contract addresses', async () => {
    expect(uniswapLP.router).toEqual(
      '0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45'
    );
    expect(uniswapLP.nftManager).toEqual(
      '0xC36442b4a4522E871399CD717aBDD847Ab11FE88'
    );
  });

  it('Should return correct contract abi', async () => {
    expect(Array.isArray(uniswapLP.routerAbi)).toEqual(true);
    expect(Array.isArray(uniswapLP.nftAbi)).toEqual(true);
    expect(Array.isArray(uniswapLP.poolAbi)).toEqual(true);
  });

  it('addPositionHelper returns calldata and value', async () => {
    patchPoolState();
    patchAlphaRouter();

    const callData = await uniswapLP.addPositionHelper(
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

    const callData = await uniswapLP.reducePositionHelper(wallet, 1, 100);
    expect(callData).toHaveProperty('calldata');
    expect(callData).toHaveProperty('value');
  });

  it('basic functions should work', async () => {
    patchContract();
    patchPoolState();

    expect(uniswapLP.ready()).toEqual(true);
    expect(uniswapLP.gasLimitEstimate).toBeGreaterThan(0);
    expect(typeof uniswapLP.getContract('nft', ethereum.provider)).toEqual(
      'object'
    );
    expect(
      typeof uniswapLP.getPoolContract(
        '0x4F96Fe3b7A6Cf9725f59d353F723c1bDb64CA6Aa',
        wallet
      )
    ).toEqual('object');
  });

  it('generateOverrides returns overrides correctly', async () => {
    const overrides = uniswapLP.generateOverrides(
      1,
      2,
      3,
      BigNumber.from(4),
      BigNumber.from(5),
      '6'
    );
    expect(overrides.gasLimit).toEqual(BigNumber.from('1'));
    expect(overrides.gasPrice).toBeUndefined();
    expect(overrides.nonce).toEqual(BigNumber.from(3));
    expect(overrides.maxFeePerGas as BigNumber).toEqual(BigNumber.from(4));
    expect(overrides.maxPriorityFeePerGas as BigNumber).toEqual(
      BigNumber.from(5)
    );
    expect(overrides.value).toEqual(BigNumber.from('6'));
  });

  it('reducePosition should work', async () => {
    patchPoolState();
    patchContract();

    const reduceTx = (await uniswapLP.reducePosition(
      wallet,
      1,
      100,
      50000,
      10
    )) as Transaction;
    expect(reduceTx.hash).toEqual(
      '0x75f98675a8f64dcf14927ccde9a1d59b67fa09b72cc2642ad055dae4074853d9' // noqa: mock
    );
  });

  it('addPosition should work', async () => {
    patchPoolState();
    patchWallet();
    patchAlphaRouter();

    const addTx = await uniswapLP.addPosition(
      wallet,
      DAI,
      WETH,
      '10',
      '10',
      500,
      1,
      10,
      0,
      1,
      1
    );
    expect(addTx.hash).toEqual(
      '0x75f98675a8f64dcf14927ccde9a1d59b67fa09b72cc2642ad055dae4074853d9' // noqa: mock
    );
  });

  it('collectFees should work', async () => {
    patchContract();

    const collectTx = (await uniswapLP.collectFees(wallet, 1)) as Transaction;
    expect(collectTx.hash).toEqual(
      '0x75f98675a8f64dcf14927ccde9a1d59b67fa09b72cc2642ad055dae4074853d9' // noqa: mock
    );
  });
});
