import Controller from "./controller.interface";
import { NextFunction, Request, Response, Router } from "express";
import Mango from "./mango";
import { patchInternalMarketName } from "./utils";
import {
  getAllMarkets,
  MarketConfig,
} from "@blockworks-foundation/mango-client";

/**
 * Houses every non-ftx style, mango specific information
 */
export class AccountController implements Controller {
  public path = "/api/mango";
  public router = Router();

  constructor(public mangoSimpleClient: Mango) {
    this.initializeRoutes();
  }

  private initializeRoutes() {
    // GET /account
    this.router.get(`${this.path}/account`, this.fetchMangoAccount);
  }

  private fetchMangoAccount = async (
    request: Request,
    response: Response,
    next: NextFunction
  ) => {
    const accountInternalDto = this.fetchAccountInternal();
    response.send({
      success: true,
      result: accountInternalDto,
    } as AccountDto);
  };

  private fetchAccountInternal(): AccountInternalDto {
    let allMarketConfigs = getAllMarkets(
      this.mangoSimpleClient.mangoGroupConfig
    );

    const spotOpenOrdersAccountDtos = allMarketConfigs
      // filter only spot markets
      .filter((marketConfig) => !marketConfig.name.includes("PERP"))
      .map((spotMarketConfig) =>
        this.getSpotOpenOrdersAccountForMarket(spotMarketConfig)
      )
      // filter markets where a spotOpenOrdersAccount exists
      .filter(
        (spotOpenOrdersAccount) => spotOpenOrdersAccount.publicKey != null
      );
    return {
      spotOpenOrdersAccounts: spotOpenOrdersAccountDtos,
    } as AccountInternalDto;
  }

  private getSpotOpenOrdersAccountForMarket(
    marketConfig: MarketConfig
  ): SpotOpenOrdersAccountDto {
    const spotOpenOrdersAccount =
      this.mangoSimpleClient.getSpotOpenOrdersAccount(marketConfig);

    return {
      name: patchInternalMarketName(marketConfig.name),
      publicKey: spotOpenOrdersAccount
        ? spotOpenOrdersAccount.toBase58()
        : null,
    } as SpotOpenOrdersAccountDto;
  }
}

/**
 * {
  "success": true,
  "result": {
    "spotOpenOrdersAccounts": [
      {
        "name": "MNGO-SPOT",
        "publicKey": "..."
      }
    ]
  }
}
 */
interface AccountDto {
  success: boolean;
  result: AccountInternalDto;
}

interface AccountInternalDto {
  spotOpenOrdersAccounts: SpotOpenOrdersAccountDto[];
}

interface SpotOpenOrdersAccountDto {
  name: string;
  publicKey: string;
}
