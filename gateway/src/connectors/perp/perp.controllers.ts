import { Transaction } from 'ethers';
import {
  HttpException,
  TOKEN_NOT_SUPPORTED_ERROR_CODE,
  TOKEN_NOT_SUPPORTED_ERROR_MESSAGE,
  INCOMPLETE_REQUEST_PARAM,
  INCOMPLETE_REQUEST_PARAM_CODE,
  UNKNOWN_ERROR_ERROR_CODE,
  UNKNOWN_ERROR_MESSAGE,
} from '../../services/error-handler';
import { TokenInfo } from '../../services/ethereum-base';
import { latency, gasCostInEthString } from '../../services/base';
import {
  Ethereumish,
  Tokenish,
  Perpish,
} from '../../services/common-interfaces';
import { logger } from '../../services/logger';
import {
  EstimateGasResponse,
  PriceRequest,
  PerpPricesResponse,
  PerpCreateTakerRequest,
  PerpCreateTakerResponse,
  PerpAvailablePairsResponse,
  PerpPositionRequest,
  PerpPositionResponse,
  PerpMarketRequest,
  PerpMarketResponse,
  PerpBalanceResponse,
} from '../../amm/amm.requests';
import { PerpPosition } from './perp';

export async function getPriceData(
  ethereumish: Ethereumish,
  perpish: Perpish,
  req: PriceRequest
): Promise<PerpPricesResponse> {
  const startTimestamp: number = Date.now();
  let prices;
  try {
    prices = await perpish.prices(`${req.base}${req.quote}`);
  } catch (e) {
    throw new HttpException(
      500,
      UNKNOWN_ERROR_MESSAGE,
      UNKNOWN_ERROR_ERROR_CODE
    );
  }

  return {
    network: ethereumish.chain,
    timestamp: startTimestamp,
    latency: latency(startTimestamp, Date.now()),
    base: req.base,
    quote: req.quote,
    markPrice: prices.markPrice.toString(),
    indexPrice: prices.indexPrice.toString(),
    indexTwapPrice: prices.indexTwapPrice.toString(),
  };
}

export async function getAvailablePairs(
  ethereumish: Ethereumish,
  perpish: Perpish
): Promise<PerpAvailablePairsResponse> {
  const startTimestamp: number = Date.now();
  return {
    network: ethereumish.chain,
    timestamp: startTimestamp,
    latency: latency(startTimestamp, Date.now()),
    pairs: perpish.availablePairs(),
  };
}

export async function checkMarketStatus(
  ethereumish: Ethereumish,
  perpish: Perpish,
  req: PerpMarketRequest
): Promise<PerpMarketResponse> {
  const startTimestamp: number = Date.now();
  const status = await perpish.isMarketActive(`${req.base}${req.quote}`);
  return {
    network: ethereumish.chain,
    timestamp: startTimestamp,
    latency: latency(startTimestamp, Date.now()),
    base: req.base,
    quote: req.quote,
    isActive: status,
  };
}

export async function getPosition(
  ethereumish: Ethereumish,
  perpish: Perpish,
  req: PerpPositionRequest
): Promise<PerpPositionResponse> {
  const startTimestamp: number = Date.now();
  const position = await perpish.getPositions(`${req.base}${req.quote}`);
  return {
    network: ethereumish.chain,
    timestamp: startTimestamp,
    latency: latency(startTimestamp, Date.now()),
    base: req.base,
    quote: req.quote,
    ...(position as PerpPosition),
  };
}

export async function createTakerOrder(
  ethereumish: Ethereumish,
  perpish: Perpish,
  req: PerpCreateTakerRequest,
  isOpen: boolean
): Promise<PerpCreateTakerResponse> {
  const startTimestamp: number = Date.now();

  const gasPrice: number = ethereumish.gasPrice;
  let tx: Transaction;

  if (isOpen) {
    if (!req.amount && !req.side) {
      throw new HttpException(
        500,
        INCOMPLETE_REQUEST_PARAM,
        INCOMPLETE_REQUEST_PARAM_CODE
      );
    }

    tx = await perpish.openPosition(
      req.side === 'LONG' ? true : false,
      `${req.base}${req.quote}`,
      req.amount as string,
      req.allowedSlippage
    );
  } else {
    tx = await perpish.closePosition(
      `${req.base}${req.quote}`,
      req.allowedSlippage
    );
  }

  await ethereumish.txStorage.saveTx(
    ethereumish.chain,
    ethereumish.chainId,
    tx.hash as string,
    new Date(),
    ethereumish.gasPrice
  );

  logger.info(
    `Order has been sent, txHash is ${tx.hash}, nonce is ${tx.nonce}, gasPrice is ${gasPrice}.`
  );

  return {
    network: ethereumish.chain,
    timestamp: startTimestamp,
    latency: latency(startTimestamp, Date.now()),
    base: req.base,
    quote: req.quote,
    amount: req.amount ? req.amount : '0',
    gasPrice: gasPrice,
    gasPriceToken: ethereumish.nativeTokenSymbol,
    gasLimit: perpish.gasLimit,
    gasCost: gasCostInEthString(gasPrice, perpish.gasLimit),
    nonce: tx.nonce,
    txHash: tx.hash,
  };
}

export function getFullTokenFromSymbol(
  ethereumish: Ethereumish,
  perpish: Perpish,
  tokenSymbol: string
): Tokenish {
  const tokenInfo: TokenInfo | undefined =
    ethereumish.getTokenBySymbol(tokenSymbol);
  let fullToken: Tokenish | undefined;
  if (tokenInfo) {
    fullToken = perpish.getTokenByAddress(tokenInfo.address);
  }
  if (!fullToken)
    throw new HttpException(
      500,
      TOKEN_NOT_SUPPORTED_ERROR_MESSAGE + tokenSymbol,
      TOKEN_NOT_SUPPORTED_ERROR_CODE
    );
  return fullToken;
}

export async function estimateGas(
  ethereumish: Ethereumish,
  perpish: Perpish
): Promise<EstimateGasResponse> {
  const gasPrice: number = ethereumish.gasPrice;
  const gasLimit: number = perpish.gasLimit;
  return {
    network: ethereumish.chain,
    timestamp: Date.now(),
    gasPrice,
    gasPriceToken: ethereumish.nativeTokenSymbol,
    gasLimit,
    gasCost: gasCostInEthString(gasPrice, gasLimit),
  };
}

export async function getAccountValue(
  ethereumish: Ethereumish,
  perpish: Perpish
): Promise<PerpBalanceResponse> {
  const startTimestamp: number = Date.now();
  let value;
  try {
    value = await perpish.getAccountValue();
  } catch (e) {
    throw new HttpException(
      500,
      UNKNOWN_ERROR_MESSAGE,
      UNKNOWN_ERROR_ERROR_CODE
    );
  }

  return {
    network: ethereumish.chain,
    timestamp: startTimestamp,
    latency: latency(startTimestamp, Date.now()),
    balance: value.toString(),
  };
}
