import Controller from "controller.interface";
import { NextFunction, Request, Response, Router } from "express";
import Mango from "src/chains/solana/mango/mango";

class CoinController implements Controller {
  public path = "/api/coins";
  public router = Router();

  constructor(public mangoSimpleClient: Mango) {
    this.initializeRoutes();
  }

  private initializeRoutes() {
    // GET /coins
    this.router.get(this.path, this.getCoins);
  }

  private getCoins = async (
    request: Request,
    response: Response,
    next: NextFunction
  ) => {
    const coinDtos = this.mangoSimpleClient.mangoGroupConfig.tokens.map(
      (tokenConfig) => {
        return {
          name: tokenConfig.symbol,
          id: tokenConfig.symbol,
        } as CoinDto;
      }
    );
    response.send({ success: true, result: coinDtos } as CoinsDto);
  };
}

export default CoinController;

/// Dtos

// e.g.
// {
//   "success": true,
//   "result": [
//     {
//       "name": "Bitcoin",
//       "id": "BTC"
//     },
//     {
//       "name": "Ethereum",
//       "id": "ETH"
//     },
//     {
//       "name": "Tether",
//       "id": "USDT"
//     },
//   ]
// }

interface CoinsDto {
  success: true;
  result: CoinDto[];
}

interface CoinDto {
  name: string;
  id: string;
}
