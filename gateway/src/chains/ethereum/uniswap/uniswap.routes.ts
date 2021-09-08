import { Router, Request, Response } from 'express';
import { Ethereum } from '../ethereum';
import { Uniswap, ExpectedTrade } from './uniswap';
import { ConfigManager } from '../../../services/config-manager';
import { HttpException, asyncHandler } from '../../../services/error-handler';
import { BigNumber } from 'ethers';
import { latency, stringWithDecimalToBigNumber } from '../../../services/base';
import { ethers } from 'ethers';
import { Trade } from '@uniswap/sdk';
import { verifyEthereumIsAvailable } from '../ethereum-middlewares';
import { verifyUniswapIsAvailable } from './uniswap-middlewares';

export namespace UniswapRoutes {
  export const router = Router();
  const uniswap = Uniswap.getInstance();
  const ethereum = Ethereum.getInstance();

  router.use(
    asyncHandler(verifyEthereumIsAvailable),
    asyncHandler(verifyUniswapIsAvailable)
  );

  router.get('/', async (_req: Request, res: Response) => {
    res.status(200).json({
      network: ConfigManager.config.ETHEREUM_CHAIN,
      uniswap_router: uniswap.uniswapRouter,
      connection: true,
      timestamp: Date.now(),
    });
  });

  type Side = 'BUY' | 'SELL';
  interface UniswapPriceRequest {
    quote: string;
    base: string;
    amount: string;
    side: Side;
  }

  interface UniswapPriceResponse {
    network: string;
    timestamp: number;
    latency: number;
    base: string;
    quote: string;
    amount: string;
    expectedAmount: string;
    price: string;
    gasPrice: number;
    gasLimit: number;
    gasCost: number;
    trade: Trade;
  }

  router.post(
    '/price',
    asyncHandler(
      async (
        req: Request<{}, {}, UniswapPriceRequest>,
        res: Response<UniswapPriceResponse, {}>
      ) => {
        const initTime = Date.now();

        let amount: BigNumber;
        if (req.body.amount.indexOf('.') > -1) {
          let token;
          if (req.body.side === 'BUY') {
            token = ethereum.getTokenBySymbol(req.body.base);
          } else {
            token = ethereum.getTokenBySymbol(req.body.quote);
          }
          if (token) {
            amount = stringWithDecimalToBigNumber(
              req.body.amount,
              token.decimals
            );
          } else {
            throw new HttpException(
              500,
              'Unrecognized quote token symbol.'
            );
          }
        } else {
          amount = BigNumber.from(req.body.amount);
        }

        const baseToken = ethereum.getTokenBySymbol(req.body.base);

        if (baseToken) {
          const quoteToken = ethereum.getTokenBySymbol(req.body.quote);
          if (quoteToken) {
            const result: ExpectedTrade | string =
              req.body.side === 'BUY'
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
                'Uniswap trade query failed: ' + result
              );
            } else {
              const trade = result.trade;
              const expectedAmount = result.expectedAmount;

              const tradePrice =
                req.body.side === 'BUY'
                  ? trade.executionPrice.invert()
                  : trade.executionPrice;

              const gasLimit = ConfigManager.config.UNISWAP_GAS_LIMIT;
              const gasPrice = ethereum.getGasPrice();
              const payload = {
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
                gasCost: gasPrice * gasLimit,
                trade: trade,
              };
              res.status(200).json(payload);
            }
          } else {
            throw new HttpException(
              500,
              'Unrecognized quote token symbol: ' + req.body.quote
            );
          }
        } else {
          throw new HttpException(
            500,
            'Unrecognized base token symbol: ' + req.body.base
          );
        }
      }
    )
  );

  interface UniswapTradeRequest {
    quote: string;
    base: string;
    amount: string;
    privateKey: string;
    side: Side;
    limitPrice?: BigNumber;
  }

  interface UniswapTradeResponse {
    network: string;
    timestamp: number;
    latency: number;
    base: string;
    quote: string;
    amount: string;
    expectedIn?: string;
    expectedOut?: string;
    price: string;
    gasPrice: number;
    gasLimit: number;
    gasCost: number;
    txHash: string | undefined;
  }

  interface UniswapTradeErrorResponse {
    error: string;
    message: string;
  }

  router.post(
    '/trade',
    asyncHandler(
      async (
        req: Request<{}, {}, UniswapTradeRequest>,
        res: Response<UniswapTradeResponse | UniswapTradeErrorResponse, {}>
      ) => {
        const initTime = Date.now();

        const limitPrice = req.body.limitPrice;

        const wallet = new ethers.Wallet(
          req.body.privateKey,
          ethereum.provider
        );

        const baseToken = ethereum.getTokenBySymbol(req.body.base);
        if (!baseToken)
          throw new HttpException(
            500,
            'Unrecognized base token symbol: ' + req.body.base
          );
        const quoteToken = ethereum.getTokenBySymbol(req.body.quote);
        if (!quoteToken)
          throw new HttpException(
            500,
            'Unrecognized quote token symbol: ' + req.body.quote
          );

        let amount: BigNumber;
        if (req.body.amount.indexOf('.') > -1) {
          let token;
          if (req.body.side === 'BUY') {
            token = ethereum.getTokenBySymbol(req.body.base);
          } else {
            token = ethereum.getTokenBySymbol(req.body.quote);
          }
          if (token) {
            amount = stringWithDecimalToBigNumber(
              req.body.amount,
              token.decimals
            );
          } else {
            throw new HttpException(
              500,
              'Unrecognized quote token symbol.'
            );
          }
        } else {
          amount = BigNumber.from(req.body.amount);
        }
          
        const result: ExpectedTrade | string =
          req.body.side === 'BUY'
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

        const gasPrice = ethereum.getGasPrice();
        const gasLimit = ConfigManager.config.UNISWAP_GAS_LIMIT;
        if (req.body.side === 'BUY') {
          const price = result.trade.executionPrice.invert();

          if (limitPrice && price.toFixed(8) >= limitPrice.toString())
            throw new HttpException(
              500,
              `Swap price ${price} exceeds limitPrice ${limitPrice}`
            );

          const tx = await uniswap.executeTrade(wallet, result.trade, gasPrice);
          return res.status(200).json({
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
            gasCost: gasPrice * gasLimit,
            txHash: tx.hash,
          });
        } else {
          const price = result.trade.executionPrice;
          if (limitPrice && price.toFixed(8) >= limitPrice.toString())
            throw new HttpException(
              500,
              `Swap price ${price} lower than limitPrice ${limitPrice}`
            );

          const tx = await uniswap.executeTrade(wallet, result.trade, gasPrice);
          return res.status(200).json({
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
            gasCost: gasPrice * gasLimit,
            txHash: tx.hash,
          });
        }
      }
    )
  );
}
