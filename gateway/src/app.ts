import express from 'express';
import { Server } from 'http';
import { Request, Response, NextFunction } from 'express';
import { EthereumRoutes } from './chains/ethereum/ethereum.routes';
import { UniswapRoutes } from './chains/ethereum/uniswap/uniswap.routes';
import { ConfigManager } from './services/config-manager';
import { logger, updateLoggerToStdout } from './services/logger';
import { addHttps } from './https';
import { asyncHandler } from './services/error-handler';

const app = express();
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
  res.send('ok');
});

interface ConfigUpdateRequest {
  APPNAME?: string;
  PORT?: number;
  IP_WHITELIST?: string[];
  HUMMINGBOT_INSTANCE_ID?: string;
  LOG_PATH?: string;
  GMT_OFFSET: number;
  CERT_PATH?: string;
  CERT_PASSPHRASE?: string;
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
    async (req: Request<{}, {}, ConfigUpdateRequest>, res: Response) => {
      let config = ConfigManager.config;

      for (const [k, v] of Object.entries(req.body)) {
        // this prevents the client from accidentally turning off HTTPS
        if (k != 'UNSAFE_DEV_MODE_WITH_HTTP' && k in config) {
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

      res.send('The config has been updated');
    }
  )
);

// handle any error thrown in the gateway api route
app.use((err: Error, _req: Request, res: Response, _next: NextFunction) => {
  const stack = err.stack || '';
  const message = err.message || 'Something went wrong';
  logger.error(message + stack);
  res.status(500).json({ message: message, stack: stack });
});

export const startGateway = async () => {
  const port = ConfigManager.config.PORT;
  logger.info(`⚡️ Gateway API listening on port ${port}`);
  if (ConfigManager.config.UNSAFE_DEV_MODE_WITH_HTTP) {
    logger.info('Running in UNSAFE HTTP! This could expose private keys.');
    server = await app.listen(port);
  } else {
    logger.info('The server is secured behind HTTPS.');
    server = await addHttps(app).listen(port);
  }
};

const stopGateway = async () => {
  return server.close();
};
