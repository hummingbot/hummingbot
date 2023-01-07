import { Injective } from './injective';
import {
  BalancesRequest,
  BalancesResponse,
  PollRequest,
  PollResponse,
  TransferToSubAccountRequest,
  TransferToSubAccountResponse,
  TransferToBankAccountRequest,
  TransferToBankAccountResponse,
} from './injective.requests';

export async function currentBlockNumber(
  injective: Injective
): Promise<number> {
  return injective.currentBlockNumber();
}

export async function transferToSubAccount(
  injective: Injective,
  req: TransferToSubAccountRequest
): Promise<TransferToSubAccountResponse> {
  const wallet = await injective.getWallet(req.address);
  return injective.transferToSubAccount(wallet, req.amount, req.token);
}

export async function transferToBankAccount(
  injective: Injective,
  req: TransferToBankAccountRequest
): Promise<TransferToBankAccountResponse> {
  const wallet = await injective.getWallet(req.address);
  return injective.transferToBankAccount(wallet, req.amount, req.token);
}

export async function balances(
  injective: Injective,
  req: BalancesRequest
): Promise<BalancesResponse> {
  const wallet = await injective.getWallet(req.address);
  return injective.balances(wallet);
}

export async function poll(
  injective: Injective,
  req: PollRequest
): Promise<PollResponse> {
  return injective.poll(req.txHash);
}
