import { Keypair, PublicKey, TransactionResponse } from '@solana/web3.js';
import { getNotNullOrThrowError } from '../../connectors/serum/serum.helpers';
import { latency, TokenValue, tokenValueToString } from '../../services/base';
import { CustomTransactionResponse } from '../../services/common-interfaces';
import {
  HttpException,
  LOAD_WALLET_ERROR_CODE,
  LOAD_WALLET_ERROR_MESSAGE,
  TOKEN_NOT_SUPPORTED_ERROR_CODE,
  TOKEN_NOT_SUPPORTED_ERROR_MESSAGE,
} from '../../services/error-handler';
import { Ripplish } from './ripple';

import {
  RippleBalanceRequest,
  RippleBalanceResponse,
  SolanaPollRequest,
  SolanaPollResponse,
  RippleTokenRequest,
  RippleTokenResponse,
} from './ripple.requests';

export async function balances(
  solanaish: Ripplish,
  req: RippleBalanceRequest
): Promise<RippleBalanceResponse | string> {
  const initTime = Date.now();
  let wallet: Keypair;
  try {
    wallet = await solanaish.getKeypair(req.address);
  } catch (err) {
    throw new HttpException(
      500,
      LOAD_WALLET_ERROR_MESSAGE + err,
      LOAD_WALLET_ERROR_CODE
    );
  }
  const balances = await solanaish.getBalances(wallet);
  const filteredBalances = toSolanaBalances(balances, req.linesSymbols);

  return {
    network: solanaish.network,
    timestamp: initTime,
    latency: latency(initTime, Date.now()),
    balances: filteredBalances,
  };
}

const toSolanaBalances = (
  balances: Record<string, TokenValue>,
  tokenSymbols: string[]
): Record<string, string> => {
  let filteredBalancesKeys = Object.keys(balances);
  if (tokenSymbols.length) {
    filteredBalancesKeys = filteredBalancesKeys.filter((symbol) =>
      tokenSymbols.includes(symbol)
    );
  }

  const solanaBalances: Record<string, string> = {};

  filteredBalancesKeys.forEach((symbol) => {
    if (balances[symbol] !== undefined)
      solanaBalances[symbol] = tokenValueToString(balances[symbol]);
    else solanaBalances[symbol] = '-1';
  });

  return solanaBalances;
};

export async function poll(
  solanaish: Ripplish,
  req: SolanaPollRequest
): Promise<SolanaPollResponse> {
  const initTime = Date.now();
  const currentBlock = await solanaish.getCurrentBlockNumber();
  const txData = getNotNullOrThrowError<TransactionResponse>(
    await solanaish.getTransaction(req.txHash)
  );
  const txStatus = await solanaish.getTransactionStatusCode(txData);

  return {
    network: solanaish.network,
    timestamp: initTime,
    currentBlock: currentBlock,
    txHash: req.txHash,
    txStatus: txStatus,
    txBlock: txData.slot,
    txData: getNotNullOrThrowError<CustomTransactionResponse>(txData),
    txReceipt: null, // TODO check if we get a receipt here
  };
}

export async function token(
  solanaish: Ripplish,
  req: RippleTokenRequest
): Promise<RippleTokenResponse> {
  const initTime = Date.now();
  const tokenInfo = solanaish.getTokenForSymbol(req.line);
  if (!tokenInfo) {
    throw new HttpException(
      500,
      TOKEN_NOT_SUPPORTED_ERROR_MESSAGE + req.line,
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
    amount = null;
  }

  return {
    network: solanaish.network,
    timestamp: initTime,
    token: req.line,
    mintAddress: mintAddress.toBase58(),
    accountAddress: account?.pubkey.toBase58(),
    amount,
  };
}

export async function getOrCreateTokenAccount(
  solanaish: Ripplish,
  req: RippleTokenRequest
): Promise<RippleTokenResponse> {
  const initTime = Date.now();
  const tokenInfo = solanaish.getTokenForSymbol(req.line);
  if (!tokenInfo) {
    throw new HttpException(
      500,
      TOKEN_NOT_SUPPORTED_ERROR_MESSAGE + req.line,
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
    amount = null;
  }

  return {
    network: solanaish.network,
    timestamp: initTime,
    token: req.line,
    mintAddress: mintAddress.toBase58(),
    accountAddress: account?.address.toBase58(),
    amount,
  };
}
