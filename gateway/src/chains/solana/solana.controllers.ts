import { latency, TokenValue, tokenValueToString } from '../../services/base';

import {
  SolanaBalanceRequest,
  SolanaBalanceResponse,
  SolanaPollRequest,
  SolanaPollResponse,
  GetSolanaTokenRequest,
  SolanaTokenResponse,
  PostSolanaTokenRequest,
} from './solana.requests';
import { Solanaish } from './solana';
import { PublicKey } from '@solana/web3.js';
import { HttpException } from '../../services/error-handler';
import { tokenSymbols } from '../../../test/services/validators.test';

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
    balances: toSolanaBalances(balances, tokenSymbols),
  };
}

const toSolanaBalances = (
  balances: Record<string, TokenValue>,
  tokenSymbols: string[]
): Record<string, string> => {
  const filteredBalancesKeys = Object.keys(balances).filter((symbol) =>
    tokenSymbols.includes(symbol)
  );
  const solanaBalances: Record<string, string> = {};

  filteredBalancesKeys.forEach(
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
  req: GetSolanaTokenRequest
): Promise<SolanaTokenResponse> {
  const initTime = Date.now();
  const tokenInfo = await solanaish.getTokenForSymbol(req.token);
  if (!tokenInfo) {
    throw new HttpException(501, 'Token not found');
  }

  const walletAddress = new PublicKey(req.publicKey);
  const mintAddress = new PublicKey(tokenInfo.address);
  const account = await solanaish.getTokenAccount(walletAddress, mintAddress);

  let amount;
  try {
    amount = tokenValueToString(
      await solanaish.getSplBalance(walletAddress, mintAddress)
    );
  } catch (err) {
    amount = undefined;
  }

  return {
    network: solanaish.cluster,
    timestamp: initTime,
    token: req.token,
    mintAddress: mintAddress.toString(),
    accountAddress: account?.owner?.toString(),
    amount,
  };
}

export async function getOrCreateTokenAccount(
  solanaish: Solanaish,
  req: PostSolanaTokenRequest
): Promise<SolanaTokenResponse> {
  const initTime = Date.now();
  const tokenInfo = await solanaish.getTokenForSymbol(req.token);
  if (!tokenInfo) {
    throw new HttpException(501, 'Token not found');
  }

  const wallet = solanaish.getWallet(req.privateKey);
  const mintAddress = new PublicKey(tokenInfo.address);
  // const account = await solanaish.getOrCreateAssociatedTokenAccount(
  //   wallet,
  //   mintAddress
  // );

  let amount;
  try {
    amount = tokenValueToString(
      await solanaish.getSplBalance(wallet.publicKey, mintAddress)
    );
  } catch (err) {
    amount = undefined;
  }

  return {
    network: solanaish.cluster,
    timestamp: initTime,
    token: req.token,
    mintAddress: mintAddress.toString(),
    accountAddress: undefined,
    amount,
  };
}
