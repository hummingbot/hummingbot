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
import { PublicKey } from '@solana/web3.js';
import {
  HttpException,
  TOKEN_NOT_SUPPORTED_ERROR_CODE,
  TOKEN_NOT_SUPPORTED_ERROR_MESSAGE,
} from '../../services/error-handler';

export async function balances(
  solanaish: Solanaish,
  req: SolanaBalanceRequest
): Promise<SolanaBalanceResponse | string> {
  const initTime = Date.now();
  const wallet = await solanaish.getKeypair(req.address);
  const balances = await solanaish.getBalances(wallet);
  const filteredBalances = toSolanaBalances(balances, req.tokenSymbols);
  if (Object.keys(filteredBalances).length === 0) {
    throw new HttpException(
      500,
      TOKEN_NOT_SUPPORTED_ERROR_MESSAGE + req.tokenSymbols,
      TOKEN_NOT_SUPPORTED_ERROR_CODE
    );
  }

  return {
    network: solanaish.cluster,
    timestamp: initTime,
    latency: latency(initTime, Date.now()),
    balances: filteredBalances,
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
  req: SolanaTokenRequest
): Promise<SolanaTokenResponse> {
  const initTime = Date.now();
  const tokenInfo = solanaish.getTokenForSymbol(req.token);
  if (!tokenInfo) {
    throw new HttpException(
      500,
      TOKEN_NOT_SUPPORTED_ERROR_MESSAGE + req.token,
      TOKEN_NOT_SUPPORTED_ERROR_CODE
    );
  }

  const walletAddress = new PublicKey(req.address);
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
    mintAddress: mintAddress.toBase58(),
    accountAddress: account?.pubkey.toBase58(),
    amount,
  };
}

export async function getOrCreateTokenAccount(
  solanaish: Solanaish,
  req: SolanaTokenRequest
): Promise<SolanaTokenResponse> {
  const initTime = Date.now();
  const tokenInfo = solanaish.getTokenForSymbol(req.token);
  if (!tokenInfo) {
    throw new HttpException(
      500,
      TOKEN_NOT_SUPPORTED_ERROR_MESSAGE + req.token,
      TOKEN_NOT_SUPPORTED_ERROR_CODE
    );
  }
  const wallet = await solanaish.getKeypair(req.address);
  const mintAddress = new PublicKey(tokenInfo.address);
  const account = await solanaish.getOrCreateAssociatedTokenAccount(
    wallet,
    mintAddress
  );

  let amount;
  try {
    const a = await solanaish.getSplBalance(wallet.publicKey, mintAddress);
    amount = tokenValueToString(a);
  } catch (err) {
    amount = undefined;
  }

  return {
    network: solanaish.cluster,
    timestamp: initTime,
    token: req.token,
    mintAddress: mintAddress.toBase58(),
    accountAddress: account?.address.toBase58(),
    amount,
  };
}
