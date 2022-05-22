import BigNumber from 'bignumber.js';
import Decimal from 'decimal.js-light';
import {
  HttpException,
  LOAD_WALLET_ERROR_CODE,
  LOAD_WALLET_ERROR_MESSAGE,
  SWAP_PRICE_EXCEEDS_LIMIT_PRICE_ERROR_CODE,
  SWAP_PRICE_EXCEEDS_LIMIT_PRICE_ERROR_MESSAGE,
  SWAP_PRICE_LOWER_THAN_LIMIT_PRICE_ERROR_CODE,
  SWAP_PRICE_LOWER_THAN_LIMIT_PRICE_ERROR_MESSAGE,
  UNKNOWN_TOKEN_ERROR_CODE,
  UNKNOWN_TOKEN_ERROR_MESSAGE,
} from '../../services/error-handler';
import { latency, gasCostInEthString } from '../../services/base';
import { Ethereumish } from '../../services/common-interfaces';
import { Curve } from './curve';
import { Wallet } from 'ethers';
import {
  PriceRequest,
  PriceResponse,
  TradeRequest,
  TradeResponse,
} from '../../amm/amm.requests';
import { TokenInfo } from '../../services/ethereum-base';
import { logger } from '../../services/logger';

export async function price(
  ethereumish: Ethereumish,
  curve: Curve,
  req: PriceRequest
): Promise<PriceResponse> {
  const initTime = Date.now();
  const baseToken = req.base;

  const baseTokenInfo: TokenInfo | undefined =
    ethereumish.getTokenBySymbol(baseToken);

  if (baseTokenInfo === undefined) {
    throw new HttpException(
      404,
      UNKNOWN_TOKEN_ERROR_MESSAGE(baseToken),
      UNKNOWN_TOKEN_ERROR_CODE
    );
  } else {
    const quoteToken = req.quote;

    const quoteTokenInfo: TokenInfo | undefined =
      ethereumish.getTokenBySymbol(quoteToken);

    if (quoteTokenInfo === undefined) {
      throw new HttpException(
        404,
        UNKNOWN_TOKEN_ERROR_MESSAGE(quoteToken),
        UNKNOWN_TOKEN_ERROR_CODE
      );
    } else {
      let expectedTrade = await curve.estimateTrade(
        baseTokenInfo,
        quoteTokenInfo,
        req.amount,
        req.side
      );

      const gasPrice = ethereumish.gasPrice;
      const gasLimit = curve.gasLimit;

      return {
        network: ethereumish.chain,
        timestamp: initTime,
        latency: latency(initTime, Date.now()),
        base: baseTokenInfo.address,
        quote: quoteTokenInfo.address,
        amount: new Decimal(req.amount).toFixed(baseTokenInfo.decimals),
        expectedAmount: expectedTrade.expectedAmount,
        price: expectedTrade.outputAmount,
        gasPrice,
        gasLimit,
        gasCost: gasCostInEthString(gasPrice, gasLimit),
        rawAmount: req.amount,
        gasPriceToken: ethereumish.nativeTokenSymbol,
      };
    }
  }
}

export async function trade(
  ethereumish: Ethereumish,
  curve: Curve,
  req: TradeRequest
): Promise<TradeResponse> {
  const startTimestamp: number = Date.now();

  const { base, quote } = req;

  const baseTokenInfo: TokenInfo | undefined =
    ethereumish.getTokenBySymbol(base);

  if (baseTokenInfo === undefined) {
    throw new HttpException(
      404,
      UNKNOWN_TOKEN_ERROR_MESSAGE(base),
      UNKNOWN_TOKEN_ERROR_CODE
    );
  } else {
    const quoteTokenInfo: TokenInfo | undefined =
      ethereumish.getTokenBySymbol(quote);

    if (quoteTokenInfo === undefined) {
      throw new HttpException(
        404,
        UNKNOWN_TOKEN_ERROR_MESSAGE(quote),
        UNKNOWN_TOKEN_ERROR_CODE
      );
    } else {
      const { limitPrice, maxFeePerGas, maxPriorityFeePerGas } = req;

      let maxFeePerGasBigNumber: BigNumber | undefined;
      if (maxFeePerGas) {
        maxFeePerGasBigNumber = new BigNumber(maxFeePerGas);
      }
      let maxPriorityFeePerGasBigNumber: BigNumber | undefined;
      if (maxPriorityFeePerGas) {
        maxPriorityFeePerGasBigNumber = new BigNumber(maxPriorityFeePerGas);
      }

      let wallet: Wallet;
      try {
        wallet = await ethereumish.getWallet(req.address);
      } catch (err) {
        logger.error(`Wallet ${req.address} not available.`);
        throw new HttpException(
          500,
          LOAD_WALLET_ERROR_MESSAGE + err,
          LOAD_WALLET_ERROR_CODE
        );
      }

      let tradeInfo = await curve.estimateTrade(
        baseTokenInfo,
        quoteTokenInfo,
        req.amount,
        req.side
      );

      if (limitPrice) {
        if (req.side === 'BUY') {
          if (new Decimal(tradeInfo.outputAmount).gt(new Decimal(limitPrice))) {
            logger.error('Swap price exceeded limit price.');
            throw new HttpException(
              500,
              SWAP_PRICE_EXCEEDS_LIMIT_PRICE_ERROR_MESSAGE(
                tradeInfo.outputAmount,
                limitPrice
              ),
              SWAP_PRICE_EXCEEDS_LIMIT_PRICE_ERROR_CODE
            );
          }
        } else {
          if (new Decimal(tradeInfo.outputAmount).lt(new Decimal(limitPrice))) {
            logger.error('Swap price lower than limit price.');
            throw new HttpException(
              500,
              SWAP_PRICE_LOWER_THAN_LIMIT_PRICE_ERROR_MESSAGE(
                tradeInfo.outputAmount,
                limitPrice
              ),
              SWAP_PRICE_LOWER_THAN_LIMIT_PRICE_ERROR_CODE
            );
          }
        }
      }

      const gasPrice: number = ethereumish.gasPrice;
      const gasLimit: number = curve.gasLimit;

      const tx = await curve.executeTrade(
        wallet,
        gasPrice,
        baseTokenInfo,
        quoteTokenInfo,
        req.amount,
        req.side,
        gasLimit,
        req.nonce,
        maxFeePerGasBigNumber,
        maxPriorityFeePerGasBigNumber,
        req.allowedSlippage
      );

      logger.info(
        `Trade has been executed, txHash is ${tx.hash}, nonce is ${tx.nonce}, gasPrice is ${gasPrice}.`
      );

      return {
        network: ethereumish.chain,
        timestamp: startTimestamp,
        latency: latency(startTimestamp, Date.now()),
        base: baseTokenInfo.address,
        quote: quoteTokenInfo.address,
        amount: new Decimal(req.amount).toFixed(baseTokenInfo.decimals),
        rawAmount: req.amount,
        expectedOut: tradeInfo.expectedAmount,
        price: tradeInfo.outputAmount,
        gasPrice: gasPrice,
        gasPriceToken: ethereumish.nativeTokenSymbol,
        gasLimit,
        gasCost: gasCostInEthString(gasPrice, gasLimit),
        nonce: tx.nonce,
        txHash: tx.hash,
      };
    }
  }
}
