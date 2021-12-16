import { latency } from '../../services/base';

import {
  SolanaBalanceResponse,
  SolanaBalanceRequest,
  SolanaPollRequest,
  SolanaPollResponse,
  SolanaTransactionResponse,
  SolanaTokenRequest,
  SolanaTokenResponse,
} from './solana.requests';
import { Solanaish } from './solana';
import { TransactionResponse } from '@solana/web3.js';

export async function balances(
  solanaish: Solanaish,
  req: SolanaBalanceRequest
): Promise<SolanaBalanceResponse | string> {
  const initTime = Date.now();
  const balances: Record<string, string> = {}; // TODO: Implement

  return {
    network: solanaish.cluster,
    timestamp: initTime,
    latency: latency(initTime, Date.now()),
    balances: balances,
  };
}

export async function poll(
  solanaish: Solanaish,
  req: SolanaPollRequest
): Promise<SolanaPollResponse> {
  const initTime = Date.now();
  const currentBlock = await solanaish.getCurrentBlockNumber();
  const txData = await solanaish.getTransaction(req.txHash);
  const txBlock = 0,
    txReceipt = null,
    txStatus = 0; // TODO: Implement

  return {
    network: solanaish.cluster,
    currentBlock,
    timestamp: initTime,
    txHash: req.txHash,
    txBlock,
    txStatus,
    txData: toSolanaTransactionResponse(txData),
    txReceipt,
  };
}

const toSolanaTransactionResponse = (
  response: TransactionResponse | null
): SolanaTransactionResponse | null => {
  return null; // TODO: Implement
};

export async function token(
  solanaish: Solanaish,
  req: SolanaTokenRequest
): Promise<SolanaTokenResponse> {
  const initTime = Date.now();
  const token = '',
    mintAddress = '',
    accountAddress = '',
    amount = 0; // TODO: Implement

  return {
    network: solanaish.cluster,
    timestamp: initTime,
    token,
    mintAddress,
    accountAddress,
    amount,
  };
}
