import { PerpOrder } from "@blockworks-foundation/mango-client";
import { Order } from "@project-serum/serum/lib/market";
import { BadRequestError, RequestErrorCustom } from "dtos";
import { NextFunction, Request, Response, Router } from "express";
import { body, query, validationResult } from "express-validator";
import Controller from "./controller.interface";
import Mango from "./mango";
import { OrderInfo } from "./types";
import {
  isValidMarket,
  logger,
  patchExternalMarketName,
  patchInternalMarketName,
} from "./utils";

class OrdersController implements Controller {
  public path = "/api/orders";
  public router = Router();

  constructor(public mangoSimpleClient: Mango) {
    this.initializeRoutes();
  }

  private initializeRoutes() {
    // GET /orders?market={market_name}
    this.router.get(
      this.path,
      query("market").custom(isValidMarket).optional(),
      this.getOpenOrders
    );

    // POST /orders
    this.router.post(
      this.path,
      body("market").not().isEmpty().custom(isValidMarket),
      body("side").not().isEmpty().isIn(["sell", "buy"]),
      body("type").not().isEmpty().isIn(["limit", "market"]),
      body("size").not().isEmpty().isNumeric(),
      body("reduceOnly").isBoolean(),
      body("ioc").isBoolean(),
      body("postOnly").isBoolean(),
      body("clientId").isNumeric(),
      this.placeOrder
    );

    // // POST /orders/{order_id}/modify todo
    // this.router.post(this.path, this.modifyOrder);

    // DELETE /orders
    this.router.delete(this.path, this.cancelAllOrders);

    // DELETE /orders/{order_id}
    this.router.delete(`${this.path}/:order_id`, this.cancelOrderByOrderId);

    // DELETE /orders/by_client_id/{client_id}
    this.router.delete(
      `${this.path}/by_client_id/:client_id`,
      this.cancelOrderByClientId
    );
  }

  private getOpenOrders = async (
    request: Request,
    response: Response,
    next: NextFunction
  ) => {
    const errors = validationResult(request);
    if (!errors.isEmpty()) {
      return response
        .status(400)
        .json({ errors: errors.array() as BadRequestError[] });
    }

    const marketName = request.query.market
      ? patchExternalMarketName(String(request.query.market))
      : undefined;

    this.getOpenOrdersInternal(marketName)
      .then((orderDtos) => {
        return response.send({ success: true, result: orderDtos } as OrdersDto);
      })
      .catch((error) => {
        logger.error(`message - ${error.message}, ${error.stack}`);
        return response.status(500).send({
          errors: [{ msg: error.message } as RequestErrorCustom],
        });
      });
  };

  private placeOrder = async (
    request: Request,
    response: Response,
    next: NextFunction
  ) => {
    const errors = validationResult(request);
    if (!errors.isEmpty()) {
      return response
        .status(400)
        .json({ errors: errors.array() as BadRequestError[] });
    }

    const placeOrderDto = request.body as PlaceOrderDto;

    if (placeOrderDto.type !== "market" && placeOrderDto.price === undefined) {
      logger.error("here");
      return response.status(400).send({
        errors: [{ msg: "missing price" } as RequestErrorCustom],
      });
    }

    logger.info(`placing order`);

    this.mangoSimpleClient
      .placeOrder(
        patchExternalMarketName(placeOrderDto.market),
        placeOrderDto.side,
        placeOrderDto.size,
        placeOrderDto.price,
        // preference - market, then ioc, then postOnly, otherwise default i.e. limit
        placeOrderDto.type == "market"
          ? "market"
          : placeOrderDto.ioc
          ? "ioc"
          : placeOrderDto.postOnly
          ? "postOnly"
          : "limit",
        placeOrderDto.clientId
      )
      .then(() => {
        return response.status(200).send();
      })
      .catch((error) => {
        logger.error(`message - ${error.message}, ${error.stack}`);
        return response.status(500).send({
          errors: [{ msg: error.message } as RequestErrorCustom],
        });
      });
  };

  private cancelAllOrders = async (
    request: Request,
    response: Response,
    next: NextFunction
  ) => {
    logger.info(`cancelling all orders...`);
    this.mangoSimpleClient
      .cancelAllOrders()
      .then(() => {
        return response.status(200).send();
      })
      .catch((error) => {
        logger.error(`message - ${error.message}, ${error.stack}`);
        return response.status(500).send({
          errors: [{ msg: error.message } as RequestErrorCustom],
        });
      });
  };

  private cancelOrderByOrderId = async (
    request: Request,
    response: Response,
    next: NextFunction
  ) => {
    const orderId = request.params.order_id;
    logger.info(`cancelling order with orderId ${orderId}...`);
    this.mangoSimpleClient
      .getOrderByOrderId(orderId)
      .then((orderInfos) => {
        if (!orderInfos.length) {
          return response
            .status(400)
            .json({ errors: [{ msg: "Order not found!" }] });
        }
        this.mangoSimpleClient
          .cancelOrder(orderInfos[0])
          .then(() => response.send())
          .catch((error) => {
            logger.error(`message - ${error.message}, ${error.stack}`);
            return response
              .status(500)
              .json({ errors: [{ msg: error.message }] });
          });
      })
      .catch((error) => {
        logger.error(`message - ${error.message}, ${error.stack}`);
        return response.status(500).json({ errors: [{ msg: error.message }] });
      });
  };

  private cancelOrderByClientId = async (
    request: Request,
    response: Response,
    next: NextFunction
  ) => {
    const clientId = request.params.client_id;
    logger.info(`cancelling order with clientId ${clientId}...`);
    this.mangoSimpleClient
      .getOrderByClientId(clientId)
      .then((orderInfos) => {
        if (!orderInfos.length) {
          return response
            .status(400)
            .json({ errors: [{ msg: "Order not found!" }] });
        }
        this.mangoSimpleClient
          .cancelOrder(orderInfos[0])
          .then(() => response.send())
          .catch((error) => {
            logger.error(`message - ${error.message}, ${error.stack}`);
            return response
              .status(500)
              .json({ errors: [{ msg: error.message }] });
          });
      })
      .catch((error) => {
        logger.error(`message - ${error.message}, ${error.stack}`);
        return response.status(500).json({ errors: [{ msg: error.message }] });
      });
  };

  private async getOpenOrdersInternal(marketName: string) {
    const openOrders = await this.mangoSimpleClient.fetchAllBidsAndAsks(
      true,
      marketName
    );

    const orderDtos = openOrders.flat().map((orderInfo: OrderInfo) => {
      if ("bestInitial" in orderInfo.order) {
        const perpOrder = orderInfo.order as PerpOrder;
        return {
          createdAt: new Date(perpOrder.timestamp.toNumber() * 1000),
          filledSize: undefined,
          future: patchInternalMarketName(orderInfo.market.config.name),
          id: perpOrder.orderId.toString(),
          market: patchInternalMarketName(orderInfo.market.config.name),
          price: perpOrder.price,
          avgFillPrice: undefined,
          remainingSize: undefined,
          side: perpOrder.side,
          size: perpOrder.size,
          status: "open",
          type: "limit",
          reduceOnly: undefined,
          ioc: undefined,
          postOnly: undefined,
          clientId:
            perpOrder.clientId && perpOrder.clientId.toString() !== "0"
              ? perpOrder.clientId.toString()
              : undefined,
        } as OrderDto;
      }

      const spotOrder = orderInfo.order as Order;
      return {
        createdAt: undefined,
        filledSize: undefined,
        future: patchInternalMarketName(orderInfo.market.config.name),
        id: spotOrder.orderId.toString(),
        market: patchInternalMarketName(orderInfo.market.config.name),
        price: spotOrder.price,
        avgFillPrice: undefined,
        remainingSize: undefined,
        side: spotOrder.side,
        size: spotOrder.size,
        status: "open",
        type: undefined,
        reduceOnly: undefined,
        ioc: undefined,
        postOnly: undefined,
        clientId:
          spotOrder.clientId && spotOrder.clientId.toString() !== "0"
            ? spotOrder.clientId.toString()
            : undefined,
      } as OrderDto;
    });
    return orderDtos;
  }
}

export default OrdersController;

/// Dtos

// e.g.
// {
//   "success": true,
//   "result": [
//     {
//       "createdAt": "2019-03-05T09:56:55.728933+00:00",
//       "filledSize": 10,
//       "future": "XRP-PERP",
//       "id": 9596912,
//       "market": "XRP-PERP",
//       "price": 0.306525,
//       "avgFillPrice": 0.306526,
//       "remainingSize": 31421,
//       "side": "sell",
//       "size": 31431,
//       "status": "open",
//       "type": "limit",
//       "reduceOnly": false,
//       "ioc": false,
//       "postOnly": false,
//       "clientId": null
//     }
//   ]
// }

interface OrdersDto {
  success: boolean;
  result: OrderDto[];
}

interface OrderDto {
  createdAt: Date;
  filledSize: number;
  future: string;
  id: string;
  market: string;
  price: number;
  avgFillPrice: number;
  remainingSize: number;
  side: string;
  size: number;
  status: string;
  type: string;
  reduceOnly: boolean;
  ioc: boolean;
  postOnly: boolean;
  clientId: null;
}

// e.g.
// {
//   "market": "XRP-PERP",
//   "side": "sell",
//   "price": 0.306525,
//   "type": "limit",
//   "size": 31431.0,
//   "reduceOnly": false,
//   "ioc": false,
//   "postOnly": false,
//   "clientId": null
// }

interface PlaceOrderDto {
  market: string;
  side: "sell" | "buy";
  price: number;
  type: "limit" | "market";
  size: number;
  reduceOnly: boolean;
  ioc: boolean;
  postOnly: boolean;
  clientId: number;
}

interface PlaceOrderResponseDto {
  success: true;
  result: {
    createdAt: Date;
    filledSize: number;
    future: string;
    id: number;
    market: string;
    price: number;
    remainingSize: number;
    side: "buy" | "sell";
    size: number;
    status: "new" | "open" | "closed";
    type: "limit" | "market";
    reduceOnly: boolean;
    ioc: boolean;
    postOnly: boolean;
    clientId: string;
  };
}
