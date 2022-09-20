import { PriceResponse } from '../../vault/vault.requests';

import { Vaultish } from '../../services/common-interfaces';
import { Ethereum } from '../../chains/ethereum/ethereum';
import { utils } from 'ethers';
// import { logger } from '../../services/logger';

export class Cortex implements Vaultish {
  private static _instances: { [name: string]: Cortex };
  private ethereum: Ethereum;
  private _ready: boolean = false;
  private constructor(network: string) {
    this.ethereum = Ethereum.getInstance(network);
  }

  public static getInstance(chain: string, network: string): Cortex {
    if (Cortex._instances === undefined) {
      Cortex._instances = {};
    }
    if (!(chain + network in Cortex._instances)) {
      Cortex._instances[chain + network] = new Cortex(network);
    }
    return Cortex._instances[chain + network];
  }

  public async init() {
    if (!this.ethereum.ready()) {
      await this.ethereum.init();
    }
    this._ready = true;
  }

  public ready(): boolean {
    return this._ready;
  }

  async previewRedeem(amount: number) {
    const provider = this.ethereum.provider;
    const CORTEX_INDEX_ADDRESSES = {
      1: '0x82E4bb17a00B32e5672d5EBe122Cd45bEEfD32b3',
      4: '0x82E4bb17a00B32e5672d5EBe122Cd45bEEfD32b3',
    };
    const CXD_IDX_Address = CORTEX_INDEX_ADDRESSES[1];
    const ifacePreviewRedeem = new utils.Interface([
      'function previewRedeem(uint256 shareAmount) public view returns (uint256)',
    ]);
    const encodePreviewRedeem = ifacePreviewRedeem.encodeFunctionData(
      'previewRedeem',
      [amount.toString()]
    );
    const previewRedeemHexString = await provider.call({
      to: CXD_IDX_Address,
      data: encodePreviewRedeem,
    });
    const decodedPreviewRedeemResults = ifacePreviewRedeem.decodeFunctionResult(
      'previewRedeem',
      previewRedeemHexString
    );
    const assetAmountWithFee = decodedPreviewRedeemResults.toString();
    return { assetAmountWithFee };
  }

  async previewMint(amount: number) {
    const provider = this.ethereum.provider;
    const CORTEX_INDEX_ADDRESSES = {
      1: '0x82E4bb17a00B32e5672d5EBe122Cd45bEEfD32b3',
      4: '0x82E4bb17a00B32e5672d5EBe122Cd45bEEfD32b3',
    };
    const CXD_IDX_Address = CORTEX_INDEX_ADDRESSES[1];
    const ifacePreviewMint = new utils.Interface([
      'function previewMint(uint256 shares) public view returns (uint256)',
    ]);
    const encodePreviewMint = ifacePreviewMint.encodeFunctionData(
      'previewMint',
      [amount.toString()]
    );
    const previewMintHexString = await provider.call({
      to: CXD_IDX_Address,
      data: encodePreviewMint,
    });
    const decodedPreviewMintResults = ifacePreviewMint.decodeFunctionResult(
      'previewMint',
      previewMintHexString
    );
    const assetAmountWithFee = decodedPreviewMintResults.toString();
    return { assetAmountWithFee };
  }

  async price(tradeType: string, amount: number): Promise<PriceResponse> {
    let previewMintRedeem;
    if (tradeType == 'mint') {
      previewMintRedeem = await this.previewMint(amount);
    } else if (tradeType == 'redeem') {
      previewMintRedeem = await this.previewRedeem(amount);
    } else {
      throw new Error('tradeType needs to be "mint" or "redeem"');
    }
    return { assetAmountWithFee: previewMintRedeem.assetAmountWithFee };
  }
}
