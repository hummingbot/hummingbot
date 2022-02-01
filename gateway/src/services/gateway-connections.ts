/* eslint-disable no-inner-declarations */
/* eslint-disable @typescript-eslint/ban-types */
import { Router, Response } from 'express';
import { asyncHandler } from '../services/error-handler';
import fse from 'fs-extra';
import path from 'path';

// {connector:  uniswap,  trading_type: on_chain, chain: ethereum, network: mainnet, wallet_address: 0x-----------1}

export interface Connection {
  connector: string;
  chain: string;
  network: string;
  wallet_address: string;
  trading_type: string;
}

export type GatewayConnectorsResponse = Array<Connection>;

const ConfigDir: string = path.join(__dirname, '../../../conf/');

export async function getConnectors(): Promise<GatewayConnectorsResponse> {
  const connectorsPath = path.join(ConfigDir, 'connectors.json');
  const exists = await fse.pathExists(connectorsPath);
  if (exists) {
    const connectorsJson: string = await fse.readFile(connectorsPath, 'utf8');
    return JSON.parse(connectorsJson);
  } else {
    return [];
  }
}

export namespace GatewayConnectors {
  export const router = Router();

  router.get(
    '/connectors',
    asyncHandler(async (_req, res: Response<GatewayConnectorsResponse, {}>) => {
      res.status(200).json(await getConnectors());
    })
  );
}
