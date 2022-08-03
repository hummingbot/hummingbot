// import {
// InitializationError,
// SERVICE_UNITIALIZED_ERROR_CODE,
// SERVICE_UNITIALIZED_ERROR_MESSAGE,
// UniswapishPriceError,
// } from '../../services/error-handler';
// import { CortexConfig } from './cortex.config';
import {
  // EstimateGasResponse,
  // PriceRequest,
  PriceResponse,
  // TradeRequest,
  // TradeResponse,
} from '../../vault/vault.requests';

// import { ContractInterface } from '@ethersproject/contracts';

import {
  // NetworkSelectionRequest,
  Vaultish,
} from '../../services/common-interfaces';
import { Ethereum } from '../../chains/ethereum/ethereum';
import {
  // BigNumber,
  // Wallet,
  // Transaction,
  // Contract,
  // ContractTransaction,
  utils,
} from 'ethers';
import { logger } from '../../services/logger';

export class Cortex implements Vaultish {
  private static _instances: { [name: string]: Cortex };
  private ethereum: Ethereum;
  // private _chain;
  // private _chain: string;
  // private _router: string;
  // private _routerAbi: ContractInterface;
  // private _gasLimit: number;
  // private _ttl: number;

  // private tokenList: Record<string, Token> = {};
  private _ready: boolean = false;

  private constructor(network: string) {
    // this._chain = this.ethereum.chainId
    // const config = CortexConfig.config;
    this.ethereum = Ethereum.getInstance(network);
    // this._chain = this.ethereum.chainId;
    // this._ttl = CortexConfig.config.ttl;
    // this._routerAbi = routerAbi.abi;
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
      console.log('this.ethereum.init()');
    }
    this._ready = true;
  }

  public ready(): boolean {
    return this._ready;
  }

  async previewRedeem(
    tradeType: string,
    amount: number
  ): Promise<PriceResponse> {
    logger.info(`Fetching price data for ${tradeType}-${amount}`);
    const provider = this.ethereum.provider;
    const CORTEX_INDEX_ADDRESSES = {
      1: '0x82E4bb17a00B32e5672d5EBe122Cd45bEEfD32b3',
      4: '0x82E4bb17a00B32e5672d5EBe122Cd45bEEfD32b3',
    };
    const CXD_IDX_Address = CORTEX_INDEX_ADDRESSES[1];
    const ifacePreviewRedeem = new utils.Interface([
      'function previewRedeem(uint256 shareAmount) public view virtual override returns (uint256)',
    ]);
    console.log('create contract function fragment');
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
    console.log(
      `decoded Preview Redeem totals: ${decodedPreviewRedeemResults}`
    );
    const assetAmountWithFee = previewRedeemHexString.toString();
    return { assetAmountWithFee: assetAmountWithFee };
  }

  async previewMint(tradeType: string, amount: number) {
    logger.info(`Fetching price data for ${tradeType}-${amount}`);
    const provider = this.ethereum.provider;
    const CORTEX_INDEX_ADDRESSES = {
      1: '0x82E4bb17a00B32e5672d5EBe122Cd45bEEfD32b3',
      4: '0x82E4bb17a00B32e5672d5EBe122Cd45bEEfD32b3',
    };
    const CXD_IDX_Address = CORTEX_INDEX_ADDRESSES[1];
    const ifacePreviewMint = new utils.Interface([
      'function previewMint(uint256 shares) public view virtual override returns (uint256)',
    ]);
    console.log('create contract function fragment');
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
    console.log(`decoded Preview Mint totals: ${decodedPreviewMintResults}`);
    const assetAmountWithFee = decodedPreviewMintResults.toString();
    console.log(`new assetAmountWithFee_tostring: ${assetAmountWithFee}`);
    return { assetAmountWithFee };
  }

  async price(tradeType: string, amount: number): Promise<PriceResponse> {
    let returns_;
    if (tradeType == 'mint') {
      console.log(`trade type: ${tradeType}, amount: ${amount}`);
      returns_ = await this.previewMint(tradeType, amount);
      console.log(`returns_ .: ${returns_.assetAmountWithFee}`);
    } else if (tradeType == 'redeem') {
      returns_ = await this.previewRedeem(tradeType, amount);
    } else {
      throw new Error('tradeType needs to be "mint" or "redeem"');
    }
    return { assetAmountWithFee: returns_.assetAmountWithFee };
  }
}

// async trade(network: string, req: TradeRequest): Promise<TradeResponse> {}

// async estimateGas(
//   network: string,
//   req: NetworkSelectionRequest
// ): Promise<EstimateGasResponse> {}
