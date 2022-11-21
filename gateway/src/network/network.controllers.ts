import { Solana, Solanaish } from '../chains/solana/solana';
import {
  StatusRequest,
  StatusResponse,
  TokensRequest,
  TokensResponse,
} from './network.requests';
import { Avalanche } from '../chains/avalanche/avalanche';
import { BinanceSmartChain } from '../chains/binance-smart-chain/binance-smart-chain';
import { Ethereum } from '../chains/ethereum/ethereum';
import { Harmony } from '../chains/harmony/harmony';
import { Polygon } from '../chains/polygon/polygon';
import { TokenInfo } from '../services/ethereum-base';
import {
  HttpException,
  UNKNOWN_CHAIN_ERROR_CODE,
  UNKNOWN_KNOWN_CHAIN_ERROR_MESSAGE,
} from '../services/error-handler';
import { EthereumBase } from '../services/ethereum-base';
import { Cronos } from '../chains/cronos/cronos';
import { Near } from '../chains/near/near';
import { Nearish } from '../services/common-interfaces';

export async function getStatus(
  req: StatusRequest
): Promise<StatusResponse | StatusResponse[]> {
  const statuses: StatusResponse[] = [];
  let connections: any[] = [];
  let chain: string;
  let chainId: number;
  let rpcUrl: string;
  let currentBlockNumber: number | undefined;
  let nativeCurrency: string;

  if (req.chain) {
    if (req.chain === 'avalanche') {
      connections.push(Avalanche.getInstance(req.network as string));
    } else if (req.chain === 'binance-smart-chain') {
      connections.push(BinanceSmartChain.getInstance(req.network as string));
    } else if (req.chain === 'harmony') {
      connections.push(Harmony.getInstance(req.network as string));
    } else if (req.chain === 'ethereum') {
      connections.push(Ethereum.getInstance(req.network as string));
    } else if (req.chain === 'polygon') {
      connections.push(Polygon.getInstance(req.network as string));
    } else if (req.chain === 'solana') {
      connections.push(Solana.getInstance(req.network as string));
    } else if (req.chain === 'near') {
      connections.push(Near.getInstance(req.network as string));
    } else if (req.chain === 'cronos') {
      connections.push(await Cronos.getInstance(req.network as string));
    } else {
      throw new HttpException(
        500,
        UNKNOWN_KNOWN_CHAIN_ERROR_MESSAGE(req.chain),
        UNKNOWN_CHAIN_ERROR_CODE
      );
    }
  } else {
    const avalancheConnections = Avalanche.getConnectedInstances();
    connections = connections.concat(
      avalancheConnections ? Object.values(avalancheConnections) : []
    );

    const harmonyConnections = Harmony.getConnectedInstances();
    connections = connections.concat(
      harmonyConnections ? Object.values(harmonyConnections) : []
    );

    const ethereumConnections = Ethereum.getConnectedInstances();
    connections = connections.concat(
      ethereumConnections ? Object.values(ethereumConnections) : []
    );

    const polygonConnections = Polygon.getConnectedInstances();
    connections = connections.concat(
      polygonConnections ? Object.values(polygonConnections) : []
    );

    const solanaConnections = Solana.getConnectedInstances();
    connections = connections.concat(
      solanaConnections ? Object.values(solanaConnections) : []
    );

    const cronosConnections = Cronos.getConnectedInstances();
    connections = connections.concat(
      cronosConnections ? Object.values(cronosConnections) : []
    );

    const nearConnections = Near.getConnectedInstances();
    connections = connections.concat(
      nearConnections ? Object.values(nearConnections) : []
    );

    const bscConnections = BinanceSmartChain.getConnectedInstances();
    connections = connections.concat(
      bscConnections ? Object.values(bscConnections) : []
    );
  }

  for (const connection of connections) {
    if (!connection.ready()) {
      await connection.init();
    }
    chain = connection.chain;
    chainId = connection.chainId;
    rpcUrl = connection.rpcUrl;
    nativeCurrency = connection.nativeTokenSymbol;

    try {
      currentBlockNumber = await connection.getCurrentBlockNumber();
    } catch (_e) {
      if (await connection.provider.getNetwork()) currentBlockNumber = 1; // necessary for connectors like hedera that do not have concept of blocknumber
    }
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
  let connection: EthereumBase | Solanaish | Nearish;
  let tokens: TokenInfo[] = [];

  if (req.chain && req.network) {
    if (req.chain === 'avalanche') {
      connection = Avalanche.getInstance(req.network);
    } else if (req.chain === 'binance-smart-chain') {
      connection = BinanceSmartChain.getInstance(req.network);
    } else if (req.chain === 'harmony') {
      connection = Harmony.getInstance(req.network);
    } else if (req.chain === 'ethereum') {
      connection = Ethereum.getInstance(req.network);
    } else if (req.chain === 'polygon') {
      connection = Polygon.getInstance(req.network);
    } else if (req.chain === 'solana') {
      connection = Solana.getInstance(req.network);
    } else if (req.chain === 'near') {
      connection = Near.getInstance(req.network);
    } else if (req.chain === 'cronos') {
      connection = await Cronos.getInstance(req.network);
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
