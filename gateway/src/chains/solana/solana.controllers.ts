import { latency, TokenValue, tokenValueToString } from '../../services/base';

import {
  SolanaBalanceRequest,
  SolanaBalanceResponse,
  SolanaPollRequest,
  SolanaPollResponse,
  SolanaTokenRequest,
  SolanaTokenResponse,
} from './solana.requests';
import { Solanaish } from './solana';

export async function balances(
  solanaish: Solanaish,
  req: SolanaBalanceRequest
): Promise<SolanaBalanceResponse | string> {
  const initTime = Date.now();
  const wallet = solanaish.getWallet(req.privateKey);
  const balances = await solanaish.getBalances(wallet);

  return {
    network: solanaish.cluster,
    timestamp: initTime,
    latency: latency(initTime, Date.now()),
    balances: toSolanaBalances(balances),
  };
}

const toSolanaBalances = (
  balances: Record<string, TokenValue>,
  tokenSymbols?: string[]
): Record<string, string> => {
  const filteredBalancesKeys = tokenSymbols
    ? Object.keys(balances).filter((symbol) => symbol in tokenSymbols)
    : Object.keys(balances);
  const solanaBalances: Record<string, string> = {};

  filteredBalancesKeys.map(
    (symbol) => (solanaBalances[symbol] = tokenValueToString(balances[symbol]))
  );

  return solanaBalances;
};

export async function poll(
  solanaish: Solanaish,
  req: SolanaPollRequest
): Promise<SolanaPollResponse> {
  const initTime = Date.now();
  const currentBlock = await solanaish.getCurrentBlockNumber();
  const txData = await solanaish.getTransaction(req.txHash);
  const txStatus = await solanaish.getTransactionStatusCode(txData);

  return {
    network: solanaish.cluster,
    currentBlock,
    timestamp: initTime,
    txHash: req.txHash,
    txStatus,
    txData,
  };
}

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
