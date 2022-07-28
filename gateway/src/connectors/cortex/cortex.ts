import { CortexConfig } from './cortex.config';
import {
  EstimateGasResponse,
  PriceRequest,
  PriceResponse,
  TradeRequest,
  TradeResponse,
} from './vault.requests';

import { ContractInterface } from '@ethersproject/contracts';

import {
    NetworkSelectionRequest,
    Vaultish
} from '../../services/common-interfaces';
import { Ethereum } from '../../chains/ethereum/ethereum';
import {
  BigNumber,
  Wallet,
  Transaction,
  Contract,
  ContractTransaction,
  utils,
} from 'ethers';
import { logger } from '../../services/logger';

export class Cortex implements Vaultish {
  private constructor(network: string) {
  }

  public static getInstance(chain: string, network: string): Cortex {
  }

  async price(
      network: string,
      req: PriceRequest
  ): Promise<PriceResponse> {
    logger.info(`Fetting price data for ${req.tradeType}-${req.shares}`)
    
    const CORTEX_INDEX_ADDRESSES = {
      1: '0x82E4bb17a00B32e5672d5EBe122Cd45bEEfD32b3',
      4: '0x82E4bb17a00B32e5672d5EBe122Cd45bEEfD32b3',
    };
    const CXD_IDX_Address = CORTEX_INDEX_ADDRESS[1];
    const ifacePreviewRedeem = new utils.Interface([
      'function previewRedeem(uint256 shares)',
    ]);
    const encodePreviewRedeem = ifacePreviewRedeem.encodeFunctionData('previewRedeem', [req.shares]);
    console.log(`Encoded Request: ${encodePreviewRedeem}`);
 
    const provider = this.ethereum.provider;
    logger.info(`Provider: ${provider._network}`);
    
    const previewRedeemHexString = await provider.call({
      to: CXD_IDX_Address,
      data: encodePreviewRedeem,
     });

  async trade(
      network: string,
      req: TradeRequest
  ): Promise<TradeResponse> {
  }

  async estimateGas(
      network: string,
      req: NetworkSelectionRequest
  ): Promise<EstimateGasResponse> {
  }
}
