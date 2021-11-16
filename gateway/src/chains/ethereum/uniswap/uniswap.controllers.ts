import { BigNumber, Wallet } from 'ethers';
import { Ethereum } from '../ethereum';
import {
  HttpException,
  LOAD_WALLET_ERROR_CODE,
  LOAD_WALLET_ERROR_MESSAGE,
  TOKEN_NOT_SUPPORTED_ERROR_CODE,
  TOKEN_NOT_SUPPORTED_ERROR_MESSAGE,
  TRADE_FAILED_ERROR_CODE,
  TRADE_FAILED_ERROR_MESSAGE,
  SWAP_PRICE_EXCEEDS_LIMIT_PRICE_ERROR_CODE,
  SWAP_PRICE_EXCEEDS_LIMIT_PRICE_ERROR_MESSAGE,
} from '../../../services/error-handler';
import { Uniswap, ExpectedTrade } from './uniswap';
import {
  latency,
  gasCostInEthString,
  stringWithDecimalToBigNumber,
} from '../../../services/base';
import {
  UniswapPriceRequest,
  UniswapPriceResponse,
  UniswapTradeRequest,
  UniswapTradeResponse,
  UniswapTradeErrorResponse,
} from './uniswap.requests';
import { ConfigManager } from '../../../services/config-manager';

export const ethereum = Ethereum.getInstance();
export const uniswap = Uniswap.getInstance();

export async function price(
  req: UniswapPriceRequest
): Promise<UniswapPriceResponse> {
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
      throw new HttpException(
        500,
        TOKEN_NOT_SUPPORTED_ERROR_MESSAGE + token,
        TOKEN_NOT_SUPPORTED_ERROR_CODE
      );
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
        throw new HttpException(
          500,
          TRADE_FAILED_ERROR_MESSAGE + result,
          TRADE_FAILED_ERROR_CODE
        );
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
        };
      }
    } else {
      throw new HttpException(
        500,
        TOKEN_NOT_SUPPORTED_ERROR_MESSAGE + req.quote,
        TOKEN_NOT_SUPPORTED_ERROR_CODE
      );
    }
  } else {
    throw new HttpException(
      500,
      TOKEN_NOT_SUPPORTED_ERROR_MESSAGE + req.base,
      TOKEN_NOT_SUPPORTED_ERROR_CODE
    );
  }
}

export async function trade(
  req: UniswapTradeRequest
): Promise<UniswapTradeResponse | UniswapTradeErrorResponse> {
  const initTime = Date.now();

  const { limitPrice, maxFeePerGas, maxPriorityFeePerGas } = req;

  let maxFeePerGasBigNumber;
  if (maxFeePerGas) {
    maxFeePerGasBigNumber = BigNumber.from(maxFeePerGas);
  }
  let maxPriorityFeePerGasBigNumber;
  if (maxPriorityFeePerGas) {
    maxPriorityFeePerGasBigNumber = BigNumber.from(maxPriorityFeePerGas);
  }

  let wallet: Wallet;
  try {
    wallet = ethereum.getWallet(req.privateKey);
  } catch (err) {
    throw new HttpException(
      500,
      LOAD_WALLET_ERROR_MESSAGE + err,
      LOAD_WALLET_ERROR_CODE
    );
  }

  const baseToken = ethereum.getTokenBySymbol(req.base);
  if (!baseToken)
    throw new HttpException(
      500,
      TOKEN_NOT_SUPPORTED_ERROR_MESSAGE + req.base,
      TOKEN_NOT_SUPPORTED_ERROR_CODE
    );

  const quoteToken = ethereum.getTokenBySymbol(req.quote);
  if (!quoteToken)
    throw new HttpException(
      500,
      TOKEN_NOT_SUPPORTED_ERROR_MESSAGE + req.quote,
      TOKEN_NOT_SUPPORTED_ERROR_CODE
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
      throw new HttpException(
        500,
        TOKEN_NOT_SUPPORTED_ERROR_MESSAGE + token,
        TOKEN_NOT_SUPPORTED_ERROR_CODE
      );
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
    throw new HttpException(
      500,
      TRADE_FAILED_ERROR_MESSAGE + result,
      TRADE_FAILED_ERROR_CODE
    );

  const gasPrice = ethereum.gasPrice;
  const gasLimit = ConfigManager.config.UNISWAP_GAS_LIMIT;

  if (req.side === 'BUY') {
    const price = result.trade.executionPrice.invert();

    if (limitPrice && price.toFixed(8) >= limitPrice.toString())
      throw new HttpException(
        500,
        SWAP_PRICE_EXCEEDS_LIMIT_PRICE_ERROR_MESSAGE(price, limitPrice),
        SWAP_PRICE_EXCEEDS_LIMIT_PRICE_ERROR_CODE
      );

    const tx = await uniswap.executeTrade(
      wallet,
      result.trade,
      gasPrice,
      req.nonce,
      maxFeePerGasBigNumber,
      maxPriorityFeePerGasBigNumber
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
        SWAP_PRICE_EXCEEDS_LIMIT_PRICE_ERROR_MESSAGE(price, limitPrice),
        SWAP_PRICE_EXCEEDS_LIMIT_PRICE_ERROR_CODE
      );

    const tx = await uniswap.executeTrade(
      wallet,
      result.trade,
      gasPrice,
      req.nonce,
      maxFeePerGasBigNumber,
      maxPriorityFeePerGasBigNumber
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
