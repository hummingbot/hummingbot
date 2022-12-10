import { Wallet, TxResponse } from 'xrpl';
import { Rippleish } from './ripple';
import { latency } from '../../services/base';
import {
  HttpException,
  LOAD_WALLET_ERROR_CODE,
  LOAD_WALLET_ERROR_MESSAGE,
} from '../../services/error-handler';
import { getNotNullOrThrowError } from '../../connectors/serum/serum.helpers';

import {
  RippleBalanceRequest,
  RippleBalanceResponse,
  RipplePollRequest,
  RipplePollResponse,
} from './ripple.requests';

export async function balances(
  rippleish: Rippleish,
  req: RippleBalanceRequest
): Promise<RippleBalanceResponse> {
  const initTime = Date.now();
  let wallet: Wallet;

  try {
    wallet = await rippleish.getWallet(req.address);
  } catch (err) {
    throw new HttpException(
      500,
      LOAD_WALLET_ERROR_MESSAGE + err,
      LOAD_WALLET_ERROR_CODE
    );
  }

  const balances = await rippleish.getAllBalance(wallet);

  return {
    network: rippleish.network,
    timestamp: initTime,
    latency: latency(initTime, Date.now()),
    balances,
  };
}

export async function poll(
  rippleish: Rippleish,
  req: RipplePollRequest
): Promise<RipplePollResponse> {
  const initTime = Date.now();
  const currentLedgerIndex = await rippleish.getCurrentLedgerIndex();
  const txData = getNotNullOrThrowError<TxResponse>(
    await rippleish.getTransaction(req.txHash)
  );
  const txStatus = await rippleish.getTransactionStatusCode(txData);

  return {
    network: rippleish.network,
    timestamp: initTime,
    currentLedgerIndex: currentLedgerIndex,
    txHash: req.txHash,
    txStatus: txStatus,
    txLedgerIndex: txData.result.ledger_index,
    txData: getNotNullOrThrowError<TxResponse>(txData),
  };
}
