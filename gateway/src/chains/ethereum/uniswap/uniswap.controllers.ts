import { BigNumber, Wallet } from 'ethers';
import { Ethereum } from '../ethereum';
import { HttpException } from '../../../services/error-handler';
import { Uniswap, ExpectedTrade } from './uniswap';
import {
  latency,
  gasCostInEthString,
  stringWithDecimalToBigNumber,
} from '../../../services/base';
import { validateUniswapPriceRequest } from './uniswap.validators';
import {
  UniswapPriceRequest,
  UniswapPriceResponse,
  UniswapTradeRequest,
  UniswapTradeResponse,
  UniswapTradeErrorResponse,
} from './uniswap.requests';
import { ConfigManager } from '../../../services/config-manager';
import { validateUniswapTradeRequest } from './uniswap.validators';

export const ethereum = Ethereum.getInstance();
export const uniswap = Uniswap.getInstance();

export async function price(
  req: UniswapPriceRequest
): Promise<UniswapPriceResponse> {
  validateUniswapPriceRequest(req);
  const initTime = Date.now();

  // the amount is passed in as a string. We must validate the value.
  // If it is a strictly an integer string, we can pass it interpet it as a BigNumber.
  // If is a float string, we need to know how many decimal places it has then we can
  // convert it to a BigNumber.
  let amount: BigNumber;
  if (req.amount.indexOf('.') > -1) {
    let token;
    if (req.side === 'BUY') {
      token = ethereum.getTokenBySymbol(req.quote);
    } else {
      token = ethereum.getTokenBySymbol(req.base);
    }
    if (token) {
      amount = stringWithDecimalToBigNumber(req.amount, token.decimals);
    } else {
      throw new HttpException(500, 'Unrecognized token symbol for amount.');
    }
  } else {
    amount = BigNumber.from(req.amount);
  }

  const baseToken = ethereum.getTokenBySymbol(req.base);

  if (baseToken) {
    const quoteToken = ethereum.getTokenBySymbol(req.quote);
    if (quoteToken) {
      const result: ExpectedTrade | string =
        req.side === 'BUY'
          ? await uniswap.priceSwapOut(
              quoteToken.address, // tokenIn is quote asset
              baseToken.address, // tokenOut is base asset
              amount
            )
          : await uniswap.priceSwapIn(
              baseToken.address, // tokenIn is base asset
              quoteToken.address, // tokenOut is quote asset
              amount
            );

      if (typeof result === 'string') {
        throw new HttpException(500, 'Uniswap trade query failed: ' + result);
      } else {
        const trade = result.trade;
        const expectedAmount = result.expectedAmount;

        const tradePrice =
          req.side === 'BUY'
            ? trade.executionPrice.invert()
            : trade.executionPrice;

        const gasLimit = ConfigManager.config.UNISWAP_GAS_LIMIT;
        const gasPrice = ethereum.gasPrice;
        return {
          network: ConfigManager.config.ETHEREUM_CHAIN,
          timestamp: initTime,
          latency: latency(initTime, Date.now()),
          base: baseToken.address,
          quote: quoteToken.address,
          amount: amount.toString(),
          expectedAmount: expectedAmount.toSignificant(8),
          price: tradePrice.toSignificant(8),
          gasPrice: gasPrice,
          gasLimit: gasLimit,
          gasCost: gasCostInEthString(gasPrice, gasLimit),
          trade: trade,
        };
      }
    } else {
      throw new HttpException(
        500,
        'Unrecognized quote token symbol: ' + req.quote
      );
    }
  } else {
    throw new HttpException(500, 'Unrecognized base token symbol: ' + req.base);
  }
}

export async function trade(
  req: UniswapTradeRequest
): Promise<UniswapTradeResponse | UniswapTradeErrorResponse> {
  validateUniswapTradeRequest(req);
  const initTime = Date.now();

  const limitPrice = req.limitPrice;

  let wallet: Wallet;
  try {
    wallet = ethereum.getWallet(req.privateKey);
  } catch (err) {
    throw new Error(`Error getting wallet ${err}`);
  }

  const baseToken = ethereum.getTokenBySymbol(req.base);
  if (!baseToken)
    throw new HttpException(500, 'Unrecognized base token symbol: ' + req.base);

  const quoteToken = ethereum.getTokenBySymbol(req.quote);
  if (!quoteToken)
    throw new HttpException(
      500,
      'Unrecognized quote token symbol: ' + req.quote
    );

  let amount: BigNumber;
  if (req.amount.indexOf('.') > -1) {
    let token;
    if (req.side === 'BUY') {
      token = ethereum.getTokenBySymbol(req.quote);
    } else {
      token = ethereum.getTokenBySymbol(req.base);
    }
    if (token) {
      amount = stringWithDecimalToBigNumber(req.amount, token.decimals);
    } else {
      throw new HttpException(500, 'Unrecognized quote token symbol.');
    }
  } else {
    amount = BigNumber.from(req.amount);
  }

  const result: ExpectedTrade | string =
    req.side === 'BUY'
      ? await uniswap.priceSwapOut(
          quoteToken.address, // tokenIn is quote asset
          baseToken.address, // tokenOut is base asset
          amount
        )
      : await uniswap.priceSwapIn(
          baseToken.address, // tokenIn is base asset
          quoteToken.address, // tokenOut is quote asset
          amount
        );

  if (typeof result === 'string')
    throw new HttpException(500, 'Uniswap trade query failed: ' + result);

  const gasPrice = ethereum.gasPrice;
  const gasLimit = ConfigManager.config.UNISWAP_GAS_LIMIT;

  if (req.side === 'BUY') {
    const price = result.trade.executionPrice.invert();

    if (limitPrice && price.toFixed(8) >= limitPrice.toString())
      throw new HttpException(
        500,
        `Swap price ${price} exceeds limitPrice ${limitPrice}`
      );

    const tx = await uniswap.executeTrade(
      wallet,
      result.trade,
      gasPrice,
      req.nonce
    );

    return {
      network: ConfigManager.config.ETHEREUM_CHAIN,
      timestamp: initTime,
      latency: latency(initTime, Date.now()),
      base: baseToken.address,
      quote: quoteToken.address,
      amount: amount.toString(),
      expectedIn: result.expectedAmount.toSignificant(8),
      price: price.toSignificant(8),
      gasPrice: gasPrice,
      gasLimit: gasLimit,
      gasCost: gasCostInEthString(gasPrice, gasLimit),
      nonce: tx.nonce,
      txHash: tx.hash,
    };
  } else {
    const price = result.trade.executionPrice;
    if (limitPrice && price.toFixed(8) >= limitPrice.toString())
      throw new HttpException(
        500,
        `Swap price ${price} lower than limitPrice ${limitPrice}`
      );

    const tx = await uniswap.executeTrade(
      wallet,
      result.trade,
      gasPrice,
      req.nonce
    );
    return {
      network: ConfigManager.config.ETHEREUM_CHAIN,
      timestamp: initTime,
      latency: latency(initTime, Date.now()),
      base: baseToken.address,
      quote: quoteToken.address,
      amount: amount.toString(),
      expectedOut: result.expectedAmount.toSignificant(8),
      price: price.toSignificant(8),
      gasPrice: gasPrice,
      gasLimit,
      gasCost: gasCostInEthString(gasPrice, gasLimit),
      nonce: tx.nonce,
      txHash: tx.hash,
    };
  }
}
