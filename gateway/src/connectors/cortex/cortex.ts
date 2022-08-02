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
// import { encode } from 'bs58';
// import { getCurves } from 'crypto';

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
    // logger.info()
    return Cortex._instances[chain + network];
  }

  public async init() {
    if (!this.ethereum.ready()) {
      await this.ethereum.init();
      console.log('this.ethereum.init()');
    }
    // if (this._chain == 'ethereum' && !this.ethereum.ready())
    //   console.log('if (this.chain == ethereum ^^ ... ');  
    //   throw new InitializationError(
    //     SERVICE_UNITIALIZED_ERROR_MESSAGE('ETH'),
    //     SERVICE_UNITIALIZED_ERROR_CODE
    //   );
    this._ready = true;
  }

  public ready(): boolean {
    return this._ready;
  }

  async price(tradeType: string, amount: number): Promise<PriceResponse> {
    logger.info(`Fetching price data for ${tradeType}-${amount}`);

    const provider = this.ethereum.provider;
    // const tradeType_ = req.tradeType
    // const chain_ = chain
    const CORTEX_INDEX_ADDRESSES = {
      1: '0x82E4bb17a00B32e5672d5EBe122Cd45bEEfD32b3',
      4: '0x82E4bb17a00B32e5672d5EBe122Cd45bEEfD32b3',
    };
    const CXD_IDX_Address = CORTEX_INDEX_ADDRESSES[1];
    console.log('set cortex address');

    // const ifaceGetUsdValue = new utils.Interface([
    //   'function getUsdValue(uint256 shareAmount) view returns (uint256)',
    // ]);
    // const encodeGetUsdValue = ifaceGetUsdValue.encodeFunctionData(
    //   'getUsdValue', [234345]
    // );
    // const getUsdValueHexString = await provider.call({
    //   to: CXD_IDX_Address,
    //   data: encodeGetUsdValue,
    // }); 
    // console.log(getUsdValueHexString)

    const ifacePreviewRedeem = new utils.Interface([
      'function convertToShares(uint256 assets) public view virtual override returns (unint256)']);
    console.log('create contract function fragment')
    
    const encodePreviewRedeem = ifacePreviewRedeem.encodeFunctionData(
      'convertToShares', [amount.toString()]
    );
    console.log(`Encoded Request: ${encodePreviewRedeem}`);

    const ifaceGetPoolTotalValue = new utils.Interface([
      'function getPoolTotalValue() public view returns (uint256)']);
    const encodeGetPoolTotalValue = ifaceGetPoolTotalValue.encodeFunctionData('getPoolTotalValue');
    const getPoolTotalValueHexString = await provider.call({
      to: CXD_IDX_Address,
      data: encodeGetPoolTotalValue,
    });
    console.log(getPoolTotalValueHexString)

    // logger.info(`Provider: ${provider._network}`);

    const previewRedeemHexString = await provider.call({
      to: CXD_IDX_Address,
      data: encodePreviewRedeem,
    });
    console.log(previewRedeemHexString);
    console.log(previewRedeemHexString.toString());
    // const assetAnmount_big = BigNumber.from(previewRedeemHexString.toString());
    // console.log(assetAnmount_big)
    const assetAmountWithFee = previewRedeemHexString.toString();
    return { assetAmountWithFee: assetAmountWithFee };
  }

  // async trade(network: string, req: TradeRequest): Promise<TradeResponse> {}

  // async estimateGas(
  //   network: string,
  //   req: NetworkSelectionRequest
  // ): Promise<EstimateGasResponse> {}
}
