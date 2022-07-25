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
  }

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
