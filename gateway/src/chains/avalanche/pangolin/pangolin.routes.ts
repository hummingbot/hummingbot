import { Router, Request, Response, NextFunction } from 'express';
import { Avalanche } from '../avalanche';
import { Pangolin } from './pangolin';
import { ConfigManager } from '../../../services/config-manager';
import { HttpException, asyncHandler } from '../../../services/error-handler';
import { BigNumber, Wallet } from 'ethers';
import { latency, gasCostInEthString } from '../../../services/base';
import {
  UniswapPriceRequest,
  UniswapTradeErrorResponse,
  UniswapTradeRequest,
  UniswapTradeResponse,
} from '../../ethereum/uniswap/uniswap.requests';
import { getAmountInBigNumber, getTrade } from './pangolin.controllers';
import { PangolinPriceResponse } from './pangolin.requests';
import {
  validateUniswapPriceRequest,
  validateUniswapTradeRequest,
} from '../../ethereum/uniswap/uniswap.validators';

export namespace PangolinRoutes {
  export const router = Router();
  export const pangolin = Pangolin.getInstance();
  export const avalanche = Avalanche.getInstance();

  router.use(
    asyncHandler(async (_req: Request, _res: Response, next: NextFunction) => {
      if (!avalanche.ready()) {
        await avalanche.init();
      }
      if (!pangolin.ready()) {
        await pangolin.init();
      }
      return next();
    })
  );

  router.get('/', async (_req: Request, res: Response) => {
    res.status(200).json({
      network: ConfigManager.config.AVALANCHE_CHAIN,
      pangolin_router: pangolin.pangolinRouter,
      connection: true,
      timestamp: Date.now(),
    });
  });

  router.post(
    '/price',
    asyncHandler(
      async (
        req: Request<{}, {}, UniswapPriceRequest>,
        res: Response<PangolinPriceResponse, {}>
      ) => {
        validateUniswapPriceRequest(req.body);
        const initTime = Date.now();
        let amount: BigNumber;
        try {
          amount = getAmountInBigNumber(
            avalanche,
            req.body.amount,
            req.body.side,
            req.body.quote,
            req.body.base
          );
        } catch (error: any) {
          throw new HttpException(500, error.message);
        }

        const baseToken = avalanche.getTokenBySymbol(req.body.base);
        const quoteToken = avalanche.getTokenBySymbol(req.body.quote);

        if (!baseToken || !quoteToken)
          throw new HttpException(
            500,
            'Unrecognized base token symbol: ' + baseToken
              ? req.body.quote
              : req.body.base
          );
        let trade;
        try {
          trade = await getTrade(
            pangolin,
            req.body.side,
            quoteToken.address,
            baseToken.address,
            amount
          );
        } catch (error: any) {
          throw new HttpException(500, error.message);
        }

        res.status(200).json({
          network: ConfigManager.config.AVALANCHE_CHAIN,
          timestamp: initTime,
          latency: latency(initTime, Date.now()),
          base: baseToken.address,
          quote: quoteToken.address,
          amount: amount.toString(),
          expectedAmount: trade.expectedAmount.toSignificant(8),
          price: trade.tradePrice.toSignificant(8),
          gasPrice: avalanche.gasPrice,
          gasLimit: ConfigManager.config.UNISWAP_GAS_LIMIT,
          gasCost: gasCostInEthString(
            avalanche.gasPrice,
            ConfigManager.config.UNISWAP_GAS_LIMIT
          ),
          trade: trade.trade,
        });
      }
    )
  );

  router.post(
    '/trade',
    asyncHandler(
      async (
        req: Request<{}, {}, UniswapTradeRequest>,
        res: Response<UniswapTradeResponse | UniswapTradeErrorResponse, {}>
      ) => {
        validateUniswapTradeRequest(req.body);
        const initTime = Date.now();
        const limitPrice = req.body.limitPrice;

        let wallet: Wallet;
        try {
          wallet = avalanche.getWallet(req.body.privateKey);
        } catch (err) {
          throw new Error(`Error getting wallet ${err}`);
        }

        const baseToken = avalanche.getTokenBySymbol(req.body.base);
        const quoteToken = avalanche.getTokenBySymbol(req.body.quote);
        if (!baseToken || !quoteToken)
          throw new HttpException(
            500,
            'Unrecognized base token symbol: ' + baseToken
              ? req.body.quote
              : req.body.base
          );

        let amount: BigNumber;
        try {
          amount = getAmountInBigNumber(
            avalanche,
            req.body.amount,
            req.body.side,
            req.body.quote,
            req.body.base
          );
        } catch (error: any) {
          throw new HttpException(500, error.message);
        }

        let trade;
        try {
          trade = await getTrade(
            pangolin,
            req.body.side,
            quoteToken.address,
            baseToken.address,
            amount
          );
        } catch (error: any) {
          throw new HttpException(500, error.message);
        }

        const gasPrice = avalanche.gasPrice;
        const gasLimit = ConfigManager.config.UNISWAP_GAS_LIMIT;

        if (limitPrice && trade.tradePrice.toFixed(8) >= limitPrice.toString())
          throw new HttpException(
            500,
            req.body.side === 'BUY'
              ? `Swap price ${trade.tradePrice} exceeds limitPrice ${limitPrice}`
              : `Swap price ${trade.tradePrice} lower than limitPrice ${limitPrice}`
          );

        const tx = await pangolin.executeTrade(
          wallet,
          trade.trade,
          gasPrice,
          req.body.nonce
        );

        const response: UniswapTradeResponse = {
          network: ConfigManager.config.AVALANCHE_CHAIN,
          timestamp: initTime,
          latency: latency(initTime, Date.now()),
          base: baseToken.address,
          quote: quoteToken.address,
          amount: amount.toString(),
          price: trade.tradePrice.toSignificant(8),
          gasPrice: gasPrice,
          gasLimit: gasLimit,
          gasCost: gasCostInEthString(gasPrice, gasLimit),
          nonce: tx.nonce,
          txHash: tx.hash,
        };
        const expectedKey =
          req.body.side === 'BUY' ? 'expectedIn' : 'expectedOut';

        response[expectedKey] = trade.expectedAmount.toSignificant(8);
        return res.status(200).json(response);
      }
    )
  );
}
