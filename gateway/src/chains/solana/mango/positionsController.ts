import {
  getMarketByPublicKey,
  PerpMarket,
  ZERO_BN,
} from "@blockworks-foundation/mango-client";
import BN from "bn.js";
import Controller from "controller.interface";
import { RequestErrorCustom } from "dtos";
import { NextFunction, Request, Response, Router } from "express";
import Mango from "src/chains/solana/mango/mango";
import {
  logger,
  patchExternalMarketName,
  patchInternalMarketName,
} from "./utils";

class PositionsController implements Controller {
  public path = "/api/positions";
  public router = Router();

  constructor(public mangoSimpleClient: Mango) {
    this.initializeRoutes();
  }

  private initializeRoutes() {
    // GET /positions
    this.router.get(this.path, this.fetchPerpPositions);
  }

  private fetchPerpPositions = async (
    request: Request,
    response: Response,
    next: NextFunction
  ) => {
    this.fetchPerpPositionsInternal()
      .then((postionDtos) => {
        response.send({ success: true, result: postionDtos } as PositionsDto);
      })
      .catch((error) => {
        logger.error(`message - ${error.message}, ${error.stack}`);
        return response.status(500).send({
          errors: [{ msg: error.message } as RequestErrorCustom],
        });
      });
  };

  private async fetchPerpPositionsInternal() {
    const groupConfig = this.mangoSimpleClient.mangoGroupConfig;
    const mangoGroup = this.mangoSimpleClient.mangoGroup;

    // (re)load+fetch things
    const [mangoAccount, mangoCache, allMarkets, mangoAccountPerpFills] =
      await Promise.all([
        // a new perp account might have been created since the last fetch
        this.mangoSimpleClient.mangoAccount.reload(
          this.mangoSimpleClient.connection,
          this.mangoSimpleClient.mangoGroup.dexProgramId
        ),
        // in-order to use the fresh'est price
        this.mangoSimpleClient.mangoGroup.loadCache(
          this.mangoSimpleClient.connection
        ),
        this.mangoSimpleClient.fetchAllMarkets(),
        this.mangoSimpleClient.fetchAllPerpFills(),
      ]);

    // find perp accounts with non zero positions
    const perpAccounts = mangoAccount
      ? groupConfig.perpMarkets.map((m) => {
          return {
            perpAccount: mangoAccount.perpAccounts[m.marketIndex],
            marketIndex: m.marketIndex,
          };
        })
      : [];
    const filteredPerpAccounts = perpAccounts.filter(
      ({ perpAccount }) => !perpAccount.basePosition.eq(new BN(0))
    );

    // compute perp position details
    const postionDtos = filteredPerpAccounts.map(
      ({ perpAccount, marketIndex }, index) => {
        const perpMarketInfo =
          this.mangoSimpleClient.mangoGroup.perpMarkets[marketIndex];
        const marketConfig = getMarketByPublicKey(
          groupConfig,
          perpMarketInfo.perpMarket
        );
        const perpMarket = allMarkets[
          perpMarketInfo.perpMarket.toBase58()
        ] as PerpMarket;
        const perpTradeHistory = mangoAccountPerpFills.filter(
          (t) => t.address === marketConfig.publicKey.toBase58()
        );

        let breakEvenPrice;
        try {
          breakEvenPrice = perpAccount.getBreakEvenPrice(
            mangoAccount,
            perpMarket,
            perpTradeHistory
          );
        } catch (e) {
          breakEvenPrice = null;
        }

        const pnl =
          breakEvenPrice !== null
            ? perpMarket.baseLotsToNumber(perpAccount.basePosition) *
              (this.mangoSimpleClient.mangoGroup
                .getPrice(marketIndex, mangoCache)
                .toNumber() -
                parseFloat(breakEvenPrice.toString()))
            : null;

        let entryPrice;
        try {
          entryPrice = perpAccount.getAverageOpenPrice(
            mangoAccount,
            perpMarket,
            perpTradeHistory
          );
        } catch {
          entryPrice = 0;
        }

        return {
          cost: Math.abs(
            perpMarket.baseLotsToNumber(perpAccount.basePosition) *
              mangoGroup.getPrice(marketIndex, mangoCache).toNumber()
          ),
          cumulativeBuySize: undefined,
          cumulativeSellSize: undefined,
          entryPrice,
          estimatedLiquidationPrice: undefined,
          future: patchInternalMarketName(marketConfig.name),
          initialMarginRequirement: undefined,
          longOrderSize: undefined,
          maintenanceMarginRequirement: undefined,
          netSize: perpMarket.baseLotsToNumber(perpAccount.basePosition),
          openSize: undefined,
          realizedPnl: undefined,
          recentAverageOpenPrice: undefined,
          recentBreakEvenPrice:
            breakEvenPrice != null ? breakEvenPrice.toNumber() : null,
          recentPnl: undefined,
          shortOrderSize: undefined,
          side: perpAccount.basePosition.gt(ZERO_BN) ? "long" : "short",
          size: Math.abs(perpMarket.baseLotsToNumber(perpAccount.basePosition)),
          unrealizedPnl: pnl,
          collateralUsed: undefined,
        } as PositionDto;
      }
    );
    return postionDtos;
  }
}

export default PositionsController;

/// Dtos

// e.g.
// {
//   "success": true,
//   "result": [
//     {
//       "cost": -31.7906,
//       "cumulativeBuySize": 1.2,
//       "cumulativeSellSize": 0.0,
//       "entryPrice": 138.22,
//       "estimatedLiquidationPrice": 152.1,
//       "future": "ETH-PERP",
//       "initialMarginRequirement": 0.1,
//       "longOrderSize": 1744.55,
//       "maintenanceMarginRequirement": 0.04,
//       "netSize": -0.23,
//       "openSize": 1744.32,
//       "realizedPnl": 3.39441714,
//       "recentAverageOpenPrice": 135.31,
//       "recentBreakEvenPrice": 135.31,
//       "recentPnl": 3.1134,
//       "shortOrderSize": 1732.09,
//       "side": "sell",
//       "size": 0.23,
//       "unrealizedPnl": 0,
//       "collateralUsed": 3.17906
//     }
//   ]
// }

interface PositionsDto {
  success: boolean;
  result: PositionDto[];
}

interface PositionDto {
  cost: number;
  cumulativeBuySize: number;
  cumulativeSellSize: number;
  entryPrice: number;
  estimatedLiquidationPrice: number;
  future: string;
  initialMarginRequirement: number;
  longOrderSize: number;
  maintenanceMarginRequirement: number;
  netSize: number;
  openSize: number;
  realizedPnl: number;
  recentAverageOpenPrice: number;
  recentBreakEvenPrice: number;
  recentPnl: number;
  shortOrderSize: number;
  side: string;
  size: number;
  unrealizedPnl: number;
  collateralUsed: number;
}
