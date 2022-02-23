import { StatusRequest, StatusResponse } from './network.requests';
import { Avalanche } from '../chains/avalanche/avalanche';
import { Ethereum } from '../chains/ethereum/ethereum';
import { Harmony } from '../chains/harmony/harmony';
import {
  HttpException,
  UNKNOWN_CHAIN_ERROR_CODE,
  UNKNOWN_KNOWN_CHAIN_ERROR_MESSAGE,
} from '../services/error-handler';

export async function getStatus(
  req: StatusRequest
): Promise<StatusResponse | StatusResponse[]> {
  const statuses: StatusResponse[] = [];
  let connections: any[] = [];
  let chain: string;
  let chainId: number;
  let rpcUrl: string;
  let currentBlockNumber: number;

  if (req.chain) {
    if (req.chain === 'avalanche') {
      connections.push(Avalanche.getInstance(req.network as string));
    } else if (req.chain === 'harmony') {
      connections.push(Harmony.getInstance(req.network as string));
    } else if (req.chain === 'ethereum') {
      connections.push(Ethereum.getInstance(req.network as string));
    } else {
      throw new HttpException(
        500,
        UNKNOWN_KNOWN_CHAIN_ERROR_MESSAGE(req.chain),
        UNKNOWN_CHAIN_ERROR_CODE
      );
    }
  } else {
    const avalanceConnections = Avalanche.getConnectedInstances();
    connections = connections.concat(
      avalanceConnections ? Object.values(avalanceConnections) : []
    );
    const harmonyConnections = Harmony.getConnectedInstances();
    connections = connections.concat(
      harmonyConnections ? Object.values(harmonyConnections) : []
    );
    const ethereumConnections = Ethereum.getConnectedInstances();
    connections = connections.concat(
      ethereumConnections ? Object.values(ethereumConnections) : []
    );
  }

  for (const connection of connections) {
    chain = connection.chain;
    chainId = connection.chainId;
    rpcUrl = connection.rpcUrl;
    currentBlockNumber = await connection.getCurrentBlockNumber();
    statuses.push({
      chain,
      chainId,
      rpcUrl,
      currentBlockNumber,
    });
  }

  return req.chain ? statuses[0] : statuses;
}
