import { Wallet } from 'xrpl';
import { Ripple } from './ripple';
import { latency } from '../../services/base';
import {
  HttpException,
  LOAD_WALLET_ERROR_CODE,
  LOAD_WALLET_ERROR_MESSAGE,
} from '../../services/error-handler';

import { RippleBalanceRequest, RippleBalanceResponse } from './ripple.requests';

// TODO: Add ripple controllers
export async function balances(
  ripple: Ripple,
  req: RippleBalanceRequest
): Promise<RippleBalanceResponse> {
  const initTime = Date.now();
  let wallet: Wallet;

  try {
    wallet = await ripple.getWallet(req.address);
  } catch (err) {
    throw new HttpException(
      500,
      LOAD_WALLET_ERROR_MESSAGE + err,
      LOAD_WALLET_ERROR_CODE
    );
  }

  const balances = await ripple.getAllBalance(wallet);

  return {
    network: ripple.network,
    timestamp: initTime,
    latency: latency(initTime, Date.now()),
    balances,
  };
}
