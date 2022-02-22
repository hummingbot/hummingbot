import {
  StatusRequest,
  StatusResponse,
  TokensRequest,
  TokensResponse,
} from './network.requests';
import { Avalanche } from '../chains/avalanche/avalanche';
import { Ethereum } from '../chains/ethereum/ethereum';
import { Harmony } from '../chains/harmony/harmony';
import { Token } from '../services/ethereum-base';
import {
  HttpException,
  UNKNOWN_CHAIN_ERROR_CODE,
  UNKNOWN_KNOWN_CHAIN_ERROR_MESSAGE,
} from '../services/error-handler';
import { EthereumBase } from '../services/ethereum-base';

export async function getStatus(req: StatusRequest): Promise<StatusResponse> {
  let chain: string;
  let chainId: number;
  let rpcUrl: string;
  let currentBlockNumber: number;

  if (req.chain === 'avalanche') {
    const avalanche = Avalanche.getInstance(req.network);
    chain = avalanche.chain;
    chainId = avalanche.chainId;
    rpcUrl = avalanche.rpcUrl;
    currentBlockNumber = await avalanche.getCurrentBlockNumber();
  } else if (req.chain === 'harmony') {
    const harmony = Harmony.getInstance(req.network);
    chain = harmony.chain;
    chainId = harmony.chainId;
    rpcUrl = harmony.rpcUrl;
    currentBlockNumber = await harmony.getCurrentBlockNumber();
  } else if (req.chain === 'ethereum') {
    const ethereum = Ethereum.getInstance(req.network);
    chain = ethereum.chain;
    chainId = ethereum.chainId;
    rpcUrl = ethereum.rpcUrl;
    currentBlockNumber = await ethereum.getCurrentBlockNumber();
  } else {
    throw new HttpException(
      500,
      UNKNOWN_KNOWN_CHAIN_ERROR_MESSAGE(req.chain),
      UNKNOWN_CHAIN_ERROR_CODE
    );
  }

  return { chain, chainId, rpcUrl, currentBlockNumber };
}

export async function getTokens(req: TokensRequest): Promise<TokensResponse> {
  let connection: EthereumBase;
  let tokens: Token[] = [];

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

  if (!connection.ready()) {
    await connection.init();
  }

  if (!req.tokenSymbols) {
    tokens = connection.storedTokenList;
  } else {
    for (const t of req.tokenSymbols as []) {
      tokens.push(connection.getTokenForSymbol(t) as Token);
    }
  }

  return { tokens };
}
