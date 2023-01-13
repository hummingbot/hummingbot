import { patchEVMNonceManager } from '../../../evm.nonce.mock';

jest.useFakeTimers();
jest.setTimeout(30000);
import { Openocean } from '../../../../src/connectors/openocean/openocean';
import { UniswapishPriceError } from '../../../../src/services/error-handler';
import { Token } from '@uniswap/sdk';
import { BigNumber } from 'ethers';
import { Harmony } from '../../../../src/chains/harmony/harmony';

let harmony: Harmony;
let openocean: Openocean;

const USDC = new Token(
  1666600000,
  '0x985458e523db3d53125813ed68c274899e9dfab4',
  6,
  '1USDC'
);
const DAI = new Token(
  1666600000,
  '0xef977d2f931c1978db5f6747666fa1eacb0d0339',
  18,
  '1DAI'
);
const mooOneBIFI = new Token(
  1666600000,
  '0x6207536011918f1a0d8a53bc426f4fd54df2e5a8',
  18,
  'mooOneBIFI'
);

beforeAll(async () => {
  harmony = Harmony.getInstance('mainnet');
  patchEVMNonceManager(harmony.nonceManager);
  await harmony.init();
  openocean = Openocean.getInstance('harmony', 'mainnet');
  await openocean.init();
});

describe('verify Openocean estimateSellTrade', () => {
  it('Should return an ExpectedTrade when available', async () => {
    const expectedTrade = await openocean.estimateSellTrade(
      USDC,
      DAI,
      BigNumber.from((10 ** USDC.decimals).toString())
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should throw an error if no pair is available', async () => {
    await expect(async () => {
      await openocean.estimateSellTrade(
        USDC,
        mooOneBIFI,
        BigNumber.from((10 ** USDC.decimals).toString())
      );
    }).rejects.toThrow(UniswapishPriceError);
  });
});

describe('verify Openocean estimateBuyTrade', () => {
  it('Should return an ExpectedTrade when available', async () => {
    const expectedTrade = await openocean.estimateBuyTrade(
      USDC,
      DAI,
      BigNumber.from((10 ** DAI.decimals).toString())
    );
    expect(expectedTrade).toHaveProperty('trade');
    expect(expectedTrade).toHaveProperty('expectedAmount');
  });

  it('Should return an error if no pair is available', async () => {
    await expect(async () => {
      await openocean.estimateBuyTrade(
        USDC,
        mooOneBIFI,
        BigNumber.from((10 ** mooOneBIFI.decimals).toString())
      );
    }).rejects.toThrow(UniswapishPriceError);
  });
});
