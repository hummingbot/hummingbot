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

const { decodeTxRaw } = require('@cosmjs/proto-signing');

export async function balances(
  cosmosish: Cosmos,
  req: CosmosBalanceRequest
): Promise<CosmosBalanceResponse | string> {
  const initTime = Date.now();

  const wallet = await cosmosish.getWallet(req.address, 'cosmos');

  const { tokenSymbols } = req;

  tokenSymbols.forEach((symbol: string) => {
    const token = cosmosish.getTokenForSymbol(symbol);

    if (!token) {
      throw new HttpException(
        500,
        TOKEN_NOT_SUPPORTED_ERROR_MESSAGE + symbol,
        TOKEN_NOT_SUPPORTED_ERROR_CODE
      );
    }
  });

  const balances = await cosmosish.getBalances(wallet);
  const filteredBalances = toCosmosBalances(balances, tokenSymbols);

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
  const walletBalances: Record<string, string> = {};

  tokenSymbols.forEach((symbol) => {
    let balance = '0.0';

    if (balances[symbol]) {
      balance = tokenValueToString(balances[symbol]);
    }

    walletBalances[symbol] = balance;
  });

  return walletBalances;
};

export async function poll(
  cosmos: Cosmos,
  req: CosmosPollRequest
): Promise<CosmosPollResponse> {
  const initTime = Date.now();
  const transaction = await cosmos.getTransaction(req.txHash);
  const currentBlock = await cosmos.getCurrentBlockNumber();

  return {
    network: cosmos.chain,
    timestamp: initTime,
    txHash: req.txHash,
    currentBlock,
    txBlock: transaction.height,
    gasUsed: transaction.gasUsed,
    gasWanted: transaction.gasWanted,
    txData: decodeTxRaw(transaction.tx),
  };
}
