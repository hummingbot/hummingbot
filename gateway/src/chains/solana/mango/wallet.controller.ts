import {
  getTokenBySymbol,
  I80F48,
  nativeI80F48ToUi,
  nativeToUi,
  QUOTE_INDEX,
} from "@blockworks-foundation/mango-client";
import { OpenOrders } from "@project-serum/serum";
import Controller from "controller.interface";
import { RequestErrorCustom } from "dtos";
import e, { NextFunction, Request, Response, Router } from "express";
import { body } from "express-validator";
import { sumBy } from "lodash";
import Mango from "src/chains/solana/mango/mango";
import { Balances } from "./types";
import {
  i80f48ToPercent,
  isValidCoin,
  logger,
  patchInternalMarketName,
} from "./utils";

class WalletController implements Controller {
  public path = "/api/wallet";
  public router = Router();

  constructor(public mangoSimpleClient: Mango) {
    this.initializeRoutes();
  }

  private initializeRoutes() {
    // POST /wallet/balances
    this.router.get(`${this.path}/balances`, this.fetchBalances);

    // POST /wallet/withdrawals
    this.router.post(
      `${this.path}/withdrawals`,
      body("coin").not().isEmpty().custom(isValidCoin),
      body("size").isNumeric(),
      this.withdraw
    );
  }

  private fetchBalances = async (
    request: Request,
    response: Response,
    next: NextFunction
  ) => {
    this.fetchBalancesInternal()
      .then((balanceDtos) => {
        return response.send({
          success: true,
          result: balanceDtos,
        } as BalancesDto);
      })
      .catch((error) => {
        logger.error(`message - ${error.message}, ${error.stack}`);
        return response.status(500).send({
          errors: [{ msg: error.message } as RequestErrorCustom],
        });
      });
  };

  private async fetchBalancesInternal() {
    // local copies of mango objects
    const mangoGroupConfig = this.mangoSimpleClient.mangoGroupConfig;
    const mangoGroup = this.mangoSimpleClient.mangoGroup;

    // (re)load things which we want fresh
    const [mangoAccount, mangoCache, rootBanks] = await Promise.all([
      this.mangoSimpleClient.mangoAccount.reload(
        this.mangoSimpleClient.connection,
        this.mangoSimpleClient.mangoGroup.dexProgramId
      ),
      this.mangoSimpleClient.mangoGroup.loadCache(
        this.mangoSimpleClient.connection
      ),
      mangoGroup.loadRootBanks(this.mangoSimpleClient.connection),
    ]);

    ////// copy pasta block from mango-ui-v3
    /* tslint:disable */
    const balances: Balances[][] = new Array();

    for (const {
      marketIndex,
      baseSymbol,
      name,
    } of mangoGroupConfig.spotMarkets) {
      if (!mangoAccount || !mangoGroup) {
        return [];
      }

      const openOrders: OpenOrders =
        mangoAccount.spotOpenOrdersAccounts[marketIndex];
      const quoteCurrencyIndex = QUOTE_INDEX;

      let nativeBaseFree = 0;
      let nativeQuoteFree = 0;
      let nativeBaseLocked = 0;
      let nativeQuoteLocked = 0;
      if (openOrders) {
        nativeBaseFree = openOrders.baseTokenFree.toNumber();
        nativeQuoteFree = openOrders.quoteTokenFree
          .add((openOrders as any)["referrerRebatesAccrued"])
          .toNumber();
        nativeBaseLocked = openOrders.baseTokenTotal
          .sub(openOrders.baseTokenFree)
          .toNumber();
        nativeQuoteLocked = openOrders.quoteTokenTotal
          .sub(openOrders.quoteTokenFree)
          .toNumber();
      }

      const tokenIndex = marketIndex;

      const net = (nativeBaseLocked: number, tokenIndex: number) => {
        const amount = mangoAccount
          .getUiDeposit(
            mangoCache.rootBankCache[tokenIndex],
            mangoGroup,
            tokenIndex
          )
          .add(
            nativeI80F48ToUi(
              I80F48.fromNumber(nativeBaseLocked),
              mangoGroup.tokens[tokenIndex].decimals
            ).sub(
              mangoAccount.getUiBorrow(
                mangoCache.rootBankCache[tokenIndex],
                mangoGroup,
                tokenIndex
              )
            )
          );

        return amount;
      };

      const value = (nativeBaseLocked: number, tokenIndex: number) => {
        const amount = mangoGroup
          .getPrice(tokenIndex, mangoCache)
          .mul(net(nativeBaseLocked, tokenIndex));

        return amount;
      };

      const marketPair = [
        {
          market: null as null,
          key: `${name}`,
          symbol: baseSymbol,
          deposits: mangoAccount.getUiDeposit(
            mangoCache.rootBankCache[tokenIndex],
            mangoGroup,
            tokenIndex
          ),
          borrows: mangoAccount.getUiBorrow(
            mangoCache.rootBankCache[tokenIndex],
            mangoGroup,
            tokenIndex
          ),
          orders: nativeToUi(
            nativeBaseLocked,
            mangoGroup.tokens[tokenIndex].decimals
          ),
          unsettled: nativeToUi(
            nativeBaseFree,
            mangoGroup.tokens[tokenIndex].decimals
          ),
          net: net(nativeBaseLocked, tokenIndex),
          value: value(nativeBaseLocked, tokenIndex),
          depositRate: i80f48ToPercent(mangoGroup.getDepositRate(tokenIndex)),
          borrowRate: i80f48ToPercent(mangoGroup.getBorrowRate(tokenIndex)),
        },
        {
          market: null as null,
          key: `${name}`,
          symbol: mangoGroupConfig.quoteSymbol,
          deposits: mangoAccount.getUiDeposit(
            mangoCache.rootBankCache[quoteCurrencyIndex],
            mangoGroup,
            quoteCurrencyIndex
          ),
          borrows: mangoAccount.getUiBorrow(
            mangoCache.rootBankCache[quoteCurrencyIndex],
            mangoGroup,
            quoteCurrencyIndex
          ),
          orders: nativeToUi(
            nativeQuoteLocked,
            mangoGroup.tokens[quoteCurrencyIndex].decimals
          ),
          unsettled: nativeToUi(
            nativeQuoteFree,
            mangoGroup.tokens[quoteCurrencyIndex].decimals
          ),
          net: net(nativeQuoteLocked, quoteCurrencyIndex),
          value: value(nativeQuoteLocked, quoteCurrencyIndex),
          depositRate: i80f48ToPercent(mangoGroup.getDepositRate(tokenIndex)),
          borrowRate: i80f48ToPercent(mangoGroup.getBorrowRate(tokenIndex)),
        },
      ];
      balances.push(marketPair);
    }

    const baseBalances = balances.map((b) => b[0]);
    const quoteBalances = balances.map((b) => b[1]);
    const quoteMeta = quoteBalances[0];
    const quoteInOrders = sumBy(quoteBalances, "orders");
    const unsettled = sumBy(quoteBalances, "unsettled");

    const net: I80F48 = quoteMeta.deposits
      .add(I80F48.fromNumber(unsettled))
      .sub(quoteMeta.borrows)
      .add(I80F48.fromNumber(quoteInOrders));
    const token = getTokenBySymbol(mangoGroupConfig, quoteMeta.symbol);
    const tokenIndex = mangoGroup.getTokenIndex(token.mintKey);
    const value = net.mul(mangoGroup.getPrice(tokenIndex, mangoCache));
    /* tslint:enable */
    ////// end of copy pasta block from mango-ui-v3
    // append balances for base symbols
    const balanceDtos = baseBalances.map((baseBalance) => {
      return {
        coin: patchInternalMarketName(baseBalance.key),
        free: baseBalance.deposits.toNumber(),
        spotBorrow: baseBalance.borrows.toNumber(),
        total: baseBalance.net.toNumber(),
        usdValue: baseBalance.value.toNumber(),
        availableWithoutBorrow: baseBalance.net
          .sub(baseBalance.borrows)
          .toNumber(),
      } as BalanceDto;
    });

    // append balance for quote symbol
    balanceDtos.push({
      coin: patchInternalMarketName(
        this.mangoSimpleClient.mangoGroupConfig.quoteSymbol
      ),
      free: quoteMeta.deposits.toNumber(),
      spotBorrow: quoteMeta.borrows.toNumber(),
      total: net.toNumber(),
      usdValue: value.toNumber(),
      availableWithoutBorrow: net.sub(quoteMeta.borrows).toNumber(),
    });
    return balanceDtos;
  }

  private withdraw = async (
    request: Request,
    response: Response,
    next: NextFunction
  ) => {
    const withdrawDto = request.body as WithdrawDto;
    this.mangoSimpleClient
      .withdraw(withdrawDto.coin, withdrawDto.size)
      .then(() => {
        response.status(200);
      })
      .catch((error) => {
        logger.error(`message - ${error.message}, ${error.stack}`);
        return response.status(500).send({
          errors: [{ msg: error.message } as RequestErrorCustom],
        });
      });
  };
}

export default WalletController;

/// Dtos

// e.g.
// {
//   "success": true,
//   "result": [
//     {
//       "coin": "USDTBEAR",
//       "free": 2320.2,
//       "spotBorrow": 0.0,
//       "total": 2340.2,
//       "usdValue": 2340.2,
//       "availableWithoutBorrow": 2320.2
//     }
//   ]
// }

interface BalancesDto {
  success: boolean;
  result: BalanceDto[];
}

interface BalanceDto {
  coin: string;
  free: number;
  spotBorrow: number;
  total: number;
  usdValue: number;
  availableWithoutBorrow: number;
}

// e.g.
// {
//   "coin": "USDTBEAR",
//   "size": 20.2,
//   "address": "0x83a127952d266A6eA306c40Ac62A4a70668FE3BE",
//   "tag": null,
//   "password": "my_withdrawal_password",
//   "code": 152823
// }

interface WithdrawDto {
  coin: string;
  size: number;
  // unused
  address: undefined;
  tag: undefined;
  password: undefined;
  code: undefined;
}
