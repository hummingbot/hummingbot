jest.useFakeTimers();
import { Openocean, newFakeTrade } from '../../../../src/connectors/openocean/openocean';
import { HttpException, UniswapishPriceError } from '../../../../src/services/error-handler';
import {
  Token,
  Trade,
} from '@uniswap/sdk';
import { BigNumber, Wallet } from 'ethers';
import { Avalanche } from '../../../../src/chains/avalanche/avalanche';

let avalanche: Avalanche;
let openocean: Openocean;
let wallet: Wallet;

const USDC = new Token(
  43114,
  '0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E',
  6,
  'USDC'
);
const WAVAX = new Token(
  43114,
  '0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7',
  18,
  'WAVAX'
);
const bDAI = new Token(
  43114,
  '0x6807eD4369d9399847F306D7d835538915fA749d',
  18,
  'bDAI'
);


beforeAll(async () => {
  avalanche = Avalanche.getInstance('avalanche');
  await avalanche.init();
  wallet = new Wallet(
    '0000000000000000000000000000000000000000000000000000000000000002', // noqa: mock
    avalanche.provider
  );
  openocean = Openocean.getInstance('avalanche', 'avalanche');
  await openocean.init();
});

describe('verify Openocean estimateSellTrade', () => {
  it('Should return an ExpectedTrade when available', async () => {
    const expectedTrade = await openocean.estimateSellTrade(
      USDC,
      WAVAX,
      BigNumber.from((10 ** USDC.decimals).toString())
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should throw an error if no pair is available', async () => {

    await expect(async () => {
      await openocean.estimateSellTrade(USDC, bDAI, BigNumber.from((10 ** USDC.decimals).toString()));
    }).rejects.toThrow(UniswapishPriceError);
  });
});

describe('verify Openocean estimateBuyTrade', () => {
  it('Should return an ExpectedTrade when available', async () => {

    const expectedTrade = await openocean.estimateBuyTrade(
      USDC,
      WAVAX,
      BigNumber.from((10 ** WAVAX.decimals).toString())
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should return an error if no pair is available', async () => {

    await expect(async () => {
      await openocean.estimateBuyTrade(USDC, bDAI, BigNumber.from((10 ** bDAI.decimals).toString()));
    }).rejects.toThrow(UniswapishPriceError);
  });
});

describe('verify Openocean executeTrade', () => {
  it('Should return an Transaction when available', async () => {
    const quoteTrade = await openocean.estimateSellTrade(
      USDC,
      WAVAX,
      BigNumber.from((10 ** USDC.decimals).toString())
    );
    const gasPrice = avalanche.gasPrice;
    const expectedTrade = await openocean.executeTrade(
      wallet,
      quoteTrade.trade as Trade,
      gasPrice,
      openocean.router,
      0,
      openocean.routerAbi,
      0,
      10,
    );
    expect(expectedTrade).toHaveProperty('nonce');
  });

  it('Should return an error if no nonce is available', async () => {
    const trade = newFakeTrade(USDC,bDAI,BigNumber.from((10 ** USDC.decimals).toString()),BigNumber.from((10 ** bDAI.decimals).toString()));
    const gasPrice = avalanche.gasPrice;
    await expect(async () => {
      await openocean.executeTrade(
        wallet,
        trade,
        gasPrice,
        openocean.router,
        0,
        openocean.routerAbi,
        0,
        10,
      );
    }).rejects.toThrow(HttpException);
  });
});
