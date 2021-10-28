import express from 'express';
import { Server } from 'http';
import { Request, Response, NextFunction } from 'express';
import { EthereumRoutes } from './chains/ethereum/ethereum.routes';
import { UniswapRoutes } from './chains/ethereum/uniswap/uniswap.routes';
import { ConfigManager } from './services/config-manager';
import { logger, updateLoggerToStdout } from './services/logger';
import { addHttps } from './https';
import {
  asyncHandler,
  HttpException,
  NodeError,
  NETWORK_ERROR_CODE,
  RATE_LIMIT_ERROR_CODE,
  UNKNOWN_ERROR_ERROR_CODE,
  NETWORK_ERROR_MESSAGE,
  RATE_LIMIT_ERROR_MESSAGE,
  UNKNOWN_ERROR_MESSAGE,
} from './services/error-handler';

export const app = express();
let server: Server;

// parse body for application/json
app.use(express.json());

// parse url for application/x-www-form-urlencoded
app.use(express.urlencoded({ extended: true }));

// mount sub routers
app.use('/eth', EthereumRoutes.router);
app.use('/eth/uniswap', UniswapRoutes.router);

// a simple route to test that the server is running
app.get('/', (_req: Request, res: Response) => {
  res.status(200).json({ status: 'ok' });
});

app.get(
  '/config',
  (_req: Request, res: Response<ConfigManager.Config, any>) => {
    res.status(200).json(ConfigManager.config);
  }
);

interface ConfigUpdateRequest {
  APPNAME?: string;
  PORT?: number;
  IP_WHITELIST?: string[];
  HUMMINGBOT_INSTANCE_ID?: string;
  LOG_PATH?: string;
  GMT_OFFSET: number;
  CERT_PATH?: string;
  ETHEREUM_CHAIN?: string;
  INFURA_KEY?: string;
  ETH_GAS_STATION_ENABLE?: boolean;
  ETH_GAS_STATION_API_KEY?: string;
  ETH_GAS_STATION_GAS_LEVEL?: string;
  ETH_GAS_STATION_REFRESH_TIME?: number;
  ETH_MANUAL_GAS_PRICE?: number;
  LOG_TO_STDOUT?: boolean;
}

app.post(
  '/config/update',
  asyncHandler(
    async (
      req: Request<unknown, unknown, ConfigUpdateRequest>,
      res: Response
    ) => {
      const config = ConfigManager.config;

      for (const [k, v] of Object.entries(req.body)) {
        // this prevents the client from accidentally turning off HTTPS
        if (k != 'UNSAFE_DEV_MODE_WITH_HTTP' && k != 'VERSION' && k in config) {
          (config as any)[k] = v;
        }
      }

      logger.info('Update gateway config file.');
      ConfigManager.updateConfig(config);

      logger.info('Reloading gateway config file.');
      ConfigManager.reloadConfig();

      logger.info('Reload logger to stdout.');
      updateLoggerToStdout();

      logger.info('Reloading Ethereum routes.');
      EthereumRoutes.reload();

      logger.info('Restarting gateway.');
      await stopGateway();
      await startGateway();

      res.status(200).json({ message: 'The config has been updated' });
    }
  )
);

// handle any error thrown in the gateway api route
app.use(
  (
    err: Error | NodeError | HttpException,
    _req: Request,
    res: Response,
    _next: NextFunction
  ) => {
    const response: any = {
      message: err.message || UNKNOWN_ERROR_MESSAGE,
    };
    if (err.stack) response.stack = err.stack;
    // the default http error code is 503 for an unknown error
    let httpErrorCode = 503;
    if (err instanceof HttpException) {
      httpErrorCode = err.status;
      response.errorCode = err.errorCode;
    } else {
      response.errorCode = UNKNOWN_ERROR_ERROR_CODE;
      response.message = UNKNOWN_ERROR_MESSAGE;

      if ('code' in err) {
        switch (typeof err.code) {
          case 'string':
            // error is from ethers library
            if (
              ['NETWORK_ERROR', 'SERVER_ERROR', 'TIMEOUT'].includes(err.code)
            ) {
              response.errorCode = NETWORK_ERROR_CODE;
              response.message = NETWORK_ERROR_MESSAGE;
            }
            break;

          case 'number':
            // errors from provider, this code comes from infura
            if (err.code === -32005) {
              // we only handle rate-limit errors
              response.errorCode = RATE_LIMIT_ERROR_CODE;
              response.message = RATE_LIMIT_ERROR_MESSAGE;
            }
            break;
        }
      }
    }
    logger.error(response.message + response.stack);
    return res.status(httpErrorCode).json(response);
  }
);

export const startGateway = async () => {
  const port = ConfigManager.config.PORT;
  logger.info(`⚡️ Gateway API listening on port ${port}`);
  if (ConfigManager.config.UNSAFE_DEV_MODE_WITH_HTTP) {
    logger.info('Running in UNSAFE HTTP! This could expose private keys.');
    server = await app.listen(port);
  } else {
    server = await addHttps(app).listen(port);
    logger.info('The server is secured behind HTTPS.');
  }
};

const stopGateway = async () => {
  return server.close();
};
