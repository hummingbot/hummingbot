import Decimal from 'decimal.js-light';
import {
  HttpException,
  UNKNOWN_TOKEN_ERROR_CODE,
  UNKNOWN_TOKEN_ERROR_MESSAGE,
} from '../../services/error-handler';
import { latency, gasCostInEthString } from '../../services/base';
import { Ethereumish } from '../../services/common-interfaces';
import { Curve } from './curve';
import { PriceRequest, PriceResponse } from '../../amm/amm.requests';
import { TokenInfo } from '../../services/ethereum-base';

export async function price(
  ethereumish: Ethereumish,
  curve: Curve,
  req: PriceRequest
): Promise<PriceResponse> {
  const initTime = Date.now();
  // curve-js takes the tokens as symbols, not addresses
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
      let price: string;
      let expectedAmount: string;
      if (req.side === 'BUY') {
        price = await curve.price(quoteToken, baseToken, req.amount);
        expectedAmount = await curve.expectedAmount(
          quoteToken,
          baseToken,
          req.amount
        );
      } else {
        price = await curve.price(baseToken, quoteToken, req.amount);
        expectedAmount = await curve.expectedAmount(
          baseToken,
          quoteToken,
          req.amount
        );
      }

      const gasPrice = ethereumish.gasPrice;
      const gasLimit = curve.gasLimit;

      return {
        network: ethereumish.chain,
        timestamp: initTime,
        latency: latency(initTime, Date.now()),
        base: baseTokenInfo.address,
        quote: quoteTokenInfo.address,
        amount: new Decimal(req.amount).toFixed(baseTokenInfo.decimals),
        expectedAmount,
        price,
        gasPrice,
        gasLimit,
        gasCost: gasCostInEthString(gasPrice, gasLimit),
        rawAmount: req.amount,
        gasPriceToken: 'ETH',
      };
    }
  }
}
