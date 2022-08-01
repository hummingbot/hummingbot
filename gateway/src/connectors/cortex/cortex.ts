import {
  InitializationError,
  SERVICE_UNITIALIZED_ERROR_CODE,
  SERVICE_UNITIALIZED_ERROR_MESSAGE,
  // UniswapishPriceError,
} from '../../services/error-handler';
import { CortexConfig } from './cortex.config';
import {
  EstimateGasResponse,
  PriceRequest,
  PriceResponse,
  TradeRequest,
  TradeResponse,
} from '../../vault/vault.requests';

// import { ContractInterface } from '@ethersproject/contracts';

import {
  NetworkSelectionRequest,
  Vaultish,
} from '../../services/common-interfaces';
import { Ethereum } from '../../chains/ethereum/ethereum';
import {
  BigNumber,
  // Wallet,
  // Transaction,
  // Contract,
  // ContractTransaction,
  utils,
} from 'ethers';
import { logger } from '../../services/logger';
import { getCurves } from 'crypto';

export class Cortex implements Vaultish {
  private static _instances: { [name: string]: Cortex };
  private ethereum: Ethereum;
  private _chain: string;
  // private _router: string;
  // private _routerAbi: ContractInterface;
  private _gasLimit: number;
  // private _ttl: number;
  // private chainId;
  // private tokenList: Record<string, Token> = {};
  private _ready: boolean = false;

  private constructor(chain: string, network: string) {
    this._chain = chain;
    const config = CortexConfig.config;
    this.ethereum = Ethereum.getInstance(network);
    // this.chainId = this.ethereum.chainId;
    // this._ttl = CortexConfig.config.ttl;
    // this._routerAbi = routerAbi.abi;
  }

  public static getInstance(chain: string, network: string): Cortex {
    if (Cortex._instances === undefined) {
      Cortex._instances = {};
    }
    if (!(chain + network in Cortex._instances)) {
      Cortex._instances[chain + network] = new Cortex(chain, network);
    }
    // logger.info()
    return Cortex._instances[chain + network];
  }

  public async init() {
    if (this._chain == 'ethereum' && !this.ethereum.ready())
      throw new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE('ETH'),
        SERVICE_UNITIALIZED_ERROR_CODE
      );
    // for (const token of this.ethereum.storedTokenList) {
    //   this.tokenList[token.address] = new Token(
    //     this.chainId,
    //     token.address,
    //     token.decimals,
    //     token.symbol,
    //     token.name
    //   );
    // }
    this._ready = true;
  }

  public ready(): boolean {
    return this._ready;
  }

  async price(tradeType: string, amount: BigNumber): Promise<PriceResponse> {
    logger.info(`Fetting price data for ${tradeType}-${amount}`);

    // const tradeType_ = req.tradeType
    // const chain_ = chain
    const CORTEX_INDEX_ADDRESSES = {
      1: '0x82E4bb17a00B32e5672d5EBe122Cd45bEEfD32b3',
      4: '0x82E4bb17a00B32e5672d5EBe122Cd45bEEfD32b3',
    };
    const CXD_IDX_Address = CORTEX_INDEX_ADDRESSES[1];
    const ifacePreviewRedeem = new utils.Interface([
      'function previewRedeem(uint256 shares) public view returns (uint256)',
    ]);
    const encodePreviewRedeem = ifacePreviewRedeem.encodeFunctionData(
      amount.toString()
    );
    console.log(`Encoded Request: ${encodePreviewRedeem}`);

    const provider = this.ethereum.provider;
    logger.info(`Provider: ${provider._network}`);

    const previewRedeemHexString = await provider.call({
      to: CXD_IDX_Address,
      data: encodePreviewRedeem,
    });
    console.log(previewRedeemHexString);
    const assetAmountWithFee = previewRedeemHexString.string().number();
    return { assetAmountWithFee };
  }

  // async trade(network: string, req: TradeRequest): Promise<TradeResponse> {}

  // async estimateGas(
  //   network: string,
  //   req: NetworkSelectionRequest
  // ): Promise<EstimateGasResponse> {}
}
