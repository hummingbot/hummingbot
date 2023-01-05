import { Wallet, TxResponse } from 'xrpl';
import { XRPLish } from './xrpl';
import { latency } from '../../services/base';
import {
  HttpException,
  LOAD_WALLET_ERROR_CODE,
  LOAD_WALLET_ERROR_MESSAGE,
} from '../../services/error-handler';
import { getNotNullOrThrowError } from '../../connectors/serum/serum.helpers';

import {
  XRPLBalanceRequest,
  XRPLBalanceResponse,
  XRPLPollRequest,
  XRPLPollResponse,
} from './xrpl.requests';

export async function balances(
  xrplish: XRPLish,
  req: XRPLBalanceRequest
): Promise<XRPLBalanceResponse> {
  const initTime = Date.now();
  let wallet: Wallet;

  try {
    wallet = await xrplish.getWallet(req.address);
  } catch (err) {
    throw new HttpException(
      500,
      LOAD_WALLET_ERROR_MESSAGE + err,
      LOAD_WALLET_ERROR_CODE
    );
  }

  const balances = await xrplish.getAllBalance(wallet);

  return {
    network: xrplish.network,
    timestamp: initTime,
    latency: latency(initTime, Date.now()),
    balances,
  };
}

export async function poll(
  xrplish: XRPLish,
  req: XRPLPollRequest
): Promise<XRPLPollResponse> {
  const initTime = Date.now();
  const currentLedgerIndex = await xrplish.getCurrentLedgerIndex();
  const txData = getNotNullOrThrowError<TxResponse>(
    await xrplish.getTransaction(req.txHash)
  );
  const txStatus = await xrplish.getTransactionStatusCode(txData);

  return {
    network: xrplish.network,
    timestamp: initTime,
    currentLedgerIndex: currentLedgerIndex,
    txHash: req.txHash,
    txStatus: txStatus,
    txLedgerIndex: txData.result.ledger_index,
    txData: getNotNullOrThrowError<TxResponse>(txData),
  };
}
