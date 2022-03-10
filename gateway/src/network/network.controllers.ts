import {
  StatusRequest,
  StatusResponse,
  TokensRequest,
  TokensResponse,
} from './network.requests';
import { Avalanche } from '../chains/avalanche/avalanche';
import { Ethereum } from '../chains/ethereum/ethereum';
import { Harmony } from '../chains/harmony/harmony';
import { TokenInfo } from '../services/ethereum-base';
import {
  HttpException,
  UNKNOWN_CHAIN_ERROR_CODE,
  UNKNOWN_KNOWN_CHAIN_ERROR_MESSAGE,
} from '../services/error-handler';
import { EthereumBase } from '../services/ethereum-base';

export async function getStatus(
  req: StatusRequest
): Promise<StatusResponse | StatusResponse[]> {
  const statuses: StatusResponse[] = [];
  let connections: any[] = [];
  let chain: string;
  let chainId: number;
  let rpcUrl: string;
  let currentBlockNumber: number;
  let nativeCurrency: string;

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
    nativeCurrency = connection.nativeTokenSymbol;
    statuses.push({
      chain,
      chainId,
      rpcUrl,
      currentBlockNumber,
      nativeCurrency,
    });
  }

  return req.chain ? statuses[0] : statuses;
}

export async function getTokens(req: TokensRequest): Promise<TokensResponse> {
  let connection: EthereumBase;
  let tokens: TokenInfo[] = [];

  if (req.chain && req.network) {
    if (req.chain === 'avalanche') {
      connection = Avalanche.getInstance(req.network);
    } else if (req.chain === 'harmony') {
      connection = Harmony.getInstance(req.network);
    } else if (req.chain === 'ethereum') {
      connection = Ethereum.getInstance(req.network);
    } else {
      throw new HttpException(
        500,
        UNKNOWN_KNOWN_CHAIN_ERROR_MESSAGE(req.chain),
        UNKNOWN_CHAIN_ERROR_CODE
      );
    }
  } else {
    throw new HttpException(
      500,
      UNKNOWN_KNOWN_CHAIN_ERROR_MESSAGE(req.chain),
      UNKNOWN_CHAIN_ERROR_CODE
    );
  }

  if (!connection.ready()) {
    await connection.init();
  }

  if (!req.tokenSymbols) {
    tokens = connection.storedTokenList;
  } else {
    for (const t of req.tokenSymbols as []) {
      tokens.push(connection.getTokenForSymbol(t) as TokenInfo);
    }
  }

  return { tokens };
}
