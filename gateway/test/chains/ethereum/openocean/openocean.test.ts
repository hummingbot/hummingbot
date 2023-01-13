import { patchEVMNonceManager } from '../../../evm.nonce.mock';

jest.useFakeTimers();
jest.setTimeout(30000);
import { Openocean } from '../../../../src/connectors/openocean/openocean';
import { UniswapishPriceError } from '../../../../src/services/error-handler';
import { Token } from '@uniswap/sdk';
import { BigNumber } from 'ethers';
import { Ethereum } from '../../../../src/chains/ethereum/ethereum';

let ethereum: Ethereum;
let openocean: Openocean;

const USDC = new Token(
  1,
  '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',
  6,
  'USDC'
);
const BUSD = new Token(
  1,
  '0x4fabb145d64652a948d72533023f6e7a623c7c53',
  18,
  'BUSD'
);
const ocUSDC = new Token(
  1,
  '0x8ed9f862363ffdfd3a07546e618214b6d59f03d4',
  8,
  'ocUSDC'
);

beforeAll(async () => {
  ethereum = Ethereum.getInstance('mainnet');
  patchEVMNonceManager(ethereum.nonceManager);
  await ethereum.init();
  openocean = Openocean.getInstance('ethereum', 'mainnet');
  await openocean.init();
});

describe('verify Openocean estimateSellTrade', () => {
  it('Should return an ExpectedTrade when available', async () => {
    const expectedTrade = await openocean.estimateSellTrade(
      USDC,
      BUSD,
      BigNumber.from((10 ** USDC.decimals).toString())
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should throw an error if no pair is available', async () => {
    await expect(async () => {
      await openocean.estimateSellTrade(
        USDC,
        ocUSDC,
        BigNumber.from((10 ** USDC.decimals).toString())
      );
    }).rejects.toThrow(UniswapishPriceError);
  });
});

describe('verify Openocean estimateBuyTrade', () => {
  it('Should return an ExpectedTrade when available', async () => {
    const expectedTrade = await openocean.estimateBuyTrade(
      USDC,
      BUSD,
      BigNumber.from((10 ** BUSD.decimals).toString())
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should return an error if no pair is available', async () => {
    await expect(async () => {
      await openocean.estimateBuyTrade(
        USDC,
        ocUSDC,
        BigNumber.from((10 ** ocUSDC.decimals).toString())
      );
    }).rejects.toThrow(UniswapishPriceError);
  });
});
