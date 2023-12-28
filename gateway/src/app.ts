/* eslint-disable @typescript-eslint/ban-types */
import express from 'express';
import { ConnectorsRoutes } from './connectors/connectors.routes';

export const gatewayApp = express();

// parse body for application/json
gatewayApp.use(express.json());

// parse url for application/x-www-form-urlencoded
gatewayApp.use(express.urlencoded({ extended: true }));

gatewayApp.use('/connectors', ConnectorsRoutes.router);

export const startGateway = async (port: number) => {
  gatewayApp.listen(port, () => {
    console.log(`Gateway start at ${port}`);
  });
};
