import { Account, providers, utils } from 'near-api-js';
import { BigNumber, utils as ethersUtils } from 'ethers';
import { latency } from '../../services/base';
import {
  HttpException,
  OUT_OF_GAS_ERROR_CODE,
  OUT_OF_GAS_ERROR_MESSAGE,
  LOAD_WALLET_ERROR_CODE,
  LOAD_WALLET_ERROR_MESSAGE,
  TOKEN_NOT_SUPPORTED_ERROR_CODE,
  TOKEN_NOT_SUPPORTED_ERROR_MESSAGE,
} from '../../services/error-handler';
import { TokenInfo } from './near.base';

import {
  CancelRequest,
  CancelResponse,
  PollResponse,
  BalanceRequest,
  BalanceResponse,
} from './near.requests';
import { logger } from '../../services/logger';
import { Nearish } from '../../services/common-interfaces';

export const getTokenSymbolsToTokens = (
  near: Nearish,
  tokenSymbols: Array<string>
): Record<string, TokenInfo> => {
  const tokens: Record<string, TokenInfo> = {};

  for (let i = 0; i < tokenSymbols.length; i++) {
    const symbol = tokenSymbols[i];
    const token = near.getTokenBySymbol(symbol);
    if (token) tokens[symbol] = token;
  }

  return tokens;
};

export async function balances(
  nearish: Nearish,
  req: BalanceRequest
): Promise<BalanceResponse | string> {
  const initTime = Date.now();

  let account: Account;
  try {
    account = await nearish.getWallet(req.address);
  } catch (err) {
    throw new HttpException(
      500,
      LOAD_WALLET_ERROR_MESSAGE + err,
      LOAD_WALLET_ERROR_CODE
    );
  }
  const tokens = getTokenSymbolsToTokens(nearish, req.tokenSymbols);
  const balances: Record<string, string> = {};
  if (req.tokenSymbols.includes(nearish.nativeTokenSymbol)) {
    balances[nearish.nativeTokenSymbol] = utils.format.formatNearAmount(
      await nearish.getNativeBalance(account)
    );
  }
  await Promise.all(
    Object.keys(tokens).map(async (symbol) => {
      if (
        tokens[symbol] !== undefined &&
        symbol !== nearish.nativeTokenSymbol
      ) {
        const address = tokens[symbol].address;
        const decimals = tokens[symbol].decimals;
        // instantiate a contract and pass in provider for read-only access
        const contract = nearish.getContract(address, account);
        const balance: string = await nearish.getFungibleTokenBalance(contract);
        balances[symbol] = ethersUtils
          .formatUnits(BigNumber.from(balance), decimals)
          .toString();
      }
    })
  );

  if (!Object.keys(balances).length) {
    throw new HttpException(
      500,
      TOKEN_NOT_SUPPORTED_ERROR_MESSAGE,
      TOKEN_NOT_SUPPORTED_ERROR_CODE
    );
  }

  return {
    network: nearish.chain,
    timestamp: initTime,
    latency: latency(initTime, Date.now()),
    balances: balances,
  };
}

// txStatus
// -1: not in the mempool or failed
// 1: succeeded
export async function poll(
  nearish: Nearish,
  address: string,
  txHash: string
): Promise<PollResponse> {
  const initTime = Date.now();
  const currentBlock = await nearish.getCurrentBlockNumber();
  const txReceipt: providers.FinalExecutionOutcome =
    await nearish.getTransaction(txHash, address);
  let txStatus = -1;
  if (
    typeof txReceipt.status === 'object' &&
    'SuccessValue' in txReceipt.status
  ) {
    txStatus = 1;
  }

  if (
    txReceipt.transaction_outcome.outcome.gas_burnt /
      nearish.gasLimitTransaction >
    0.9
  ) {
    throw new HttpException(
      503,
      OUT_OF_GAS_ERROR_MESSAGE,
      OUT_OF_GAS_ERROR_CODE
    );
  }

  logger.info(`Poll ${nearish.chain}, txHash ${txHash}, status ${txStatus}.`);
  return {
    network: nearish.chain,
    currentBlock,
    timestamp: initTime,
    txHash: txHash,
    txStatus,
    txReceipt,
  };
}

export async function cancel(
  nearish: Nearish,
  req: CancelRequest
): Promise<CancelResponse> {
  const initTime = Date.now();
  let account: Account;
  try {
    account = await nearish.getWallet(req.address);
  } catch (err) {
    throw new HttpException(
      500,
      LOAD_WALLET_ERROR_MESSAGE + err,
      LOAD_WALLET_ERROR_CODE
    );
  }

  // call cancelTx function
  const cancelTx = await nearish.cancelTx(account, req.nonce);

  logger.info(
    `Cancelled transaction at nonce ${req.nonce}, cancel txHash ${cancelTx}.`
  );

  return {
    network: nearish.chain,
    timestamp: initTime,
    latency: latency(initTime, Date.now()),
    txHash: cancelTx,
  };
}
