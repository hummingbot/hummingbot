/* WIP */
import { Cosmos } from './cosmos';
import {
  CosmosBalanceRequest,
  CosmosBalanceResponse,
  CosmosPollRequest,
  CosmosPollResponse,
} from './cosmos.requests';
import { latency, TokenValue, tokenValueToString } from '../../services/base';
import {
  HttpException,
  TOKEN_NOT_SUPPORTED_ERROR_CODE,
  TOKEN_NOT_SUPPORTED_ERROR_MESSAGE,
} from '../../services/error-handler';

export async function balances(
  cosmosish: Cosmos,
  req: CosmosBalanceRequest
): Promise<CosmosBalanceResponse | string> {
  const initTime = Date.now();

  const wallet = await cosmosish.getWallet(req.address);
  const balances = await cosmosish.getBalances(wallet);
  const filteredBalances = toCosmosBalances(balances, req.tokenSymbols);

  if (Object.keys(filteredBalances).length === 0) {
    throw new HttpException(
      500,
      TOKEN_NOT_SUPPORTED_ERROR_MESSAGE + req.tokenSymbols,
      TOKEN_NOT_SUPPORTED_ERROR_CODE
    );
  }

  return {
    network: cosmosish.chain,
    timestamp: initTime,
    latency: latency(initTime, Date.now()),
    balances: filteredBalances,
  };
}

export const toCosmosBalances = (
  balances: Record<string, TokenValue>,
  tokenSymbols: Array<string>
): Record<string, string> => {
  const filteredBalancesKeys = Object.keys(balances).filter((symbol) =>
    tokenSymbols.includes(symbol)
  );

  const walletBalances: Record<string, string> = {};

  filteredBalancesKeys.forEach(
    (symbol) => (walletBalances[symbol] = tokenValueToString(balances[symbol]))
  );

  return walletBalances;
};

export async function poll(
  cosmos: Cosmos,
  req: CosmosPollRequest
): Promise<CosmosPollResponse> {
  const initTime = Date.now();
  const txData = await cosmos.getTransaction(req.txHash);

  return {
    network: cosmos.rpcUrl,
    timestamp: initTime,
    txHash: req.txHash,
    txData,
  };
}
