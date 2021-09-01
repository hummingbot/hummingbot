import { Wallet, providers } from 'ethers';
import { NextFunction, Router, Request, Response } from 'express';
import { Ethereum } from './ethereum';
import { EthereumConfig } from './ethereum.config';
import { ConfigManager } from '../../services/config-manager';
import { Token } from '../../services/ethereum-base';
import { tokenValueToString } from '../../services/base';
import { HttpException, asyncHandler } from '../../services/error-handler';
import { latency } from '../../services/base';
import { approve } from './ethereum.controllers';
export namespace EthereumRoutes {
  export const router = Router();
  let ethereum = new Ethereum();

  export const reload = (): void => {
    ethereum = new Ethereum();
  };

  router.get(
    '/',
    asyncHandler(async (_req: Request, res: Response) => {
      let rpcUrl;
      if (ConfigManager.config.ETHEREUM_CHAIN === 'mainnet') {
        rpcUrl = EthereumConfig.config.mainnet.rpcUrl;
      } else {
        rpcUrl = EthereumConfig.config.kovan.rpcUrl;
      }

      res.status(200).json({
        network: ConfigManager.config.ETHEREUM_CHAIN,
        rpcUrl: rpcUrl,
        connection: true,
        timestamp: Date.now(),
      });
    })
  );

  interface EthereumBalanceRequest {
    privateKey: string; // the users private Ethereum key
    tokenSymbols: string[]; // a list of token symbol
  }

  interface EthereumBalanceResponse {
    network: string;
    timestamp: number;
    latency: number;
    balances: Record<string, string>; // the balance should be a string encoded number
  }

  router.post(
    '/balances',
    asyncHandler(
      async (
        req: Request<{}, {}, EthereumBalanceRequest>,
        res: Response<EthereumBalanceResponse | string, {}>,
        _next: NextFunction
      ) => {
        const initTime = Date.now();

        let wallet: Wallet;
        try {
          wallet = ethereum.getWallet(req.body.privateKey);
        } catch (err) {
          throw new HttpException(500, 'Error getting wallet ' + err);
        }

        const tokenContractList: Record<string, Token> = {};

        for (var i = 0; i < req.body.tokenSymbols.length; i++) {
          const symbol = req.body.tokenSymbols[i];
          const token = ethereum.getTokenBySymbol(symbol);
          if (!token) {
            continue;
          }

          tokenContractList[symbol] = token;
        }

        const balances: Record<string, string> = {};
        balances.ETH = tokenValueToString(await ethereum.getEthBalance(wallet));
        await Promise.all(
          Object.keys(tokenContractList).map(async (symbol) => {
            if (tokenContractList[symbol] !== undefined) {
              const address = tokenContractList[symbol].address;
              const decimals = tokenContractList[symbol].decimals;
              const balance = await ethereum.getERC20Balance(
                wallet,
                address,
                decimals
              );
              balances[symbol] = tokenValueToString(balance);
            }
          })
        );

        res.status(200).json({
          network: ConfigManager.config.ETHEREUM_CHAIN,
          timestamp: initTime,
          latency: latency(initTime, Date.now()),
          balances: balances,
        });
      }
    )
  );

  interface EthereumApproveRequest {
    amount?: string;
    privateKey: string;
    spender: string;
    token: string;
  }

  interface EthereumApproveResponse {
    network: string;
    timestamp: number;
    latency: number;
    tokenAddress: string;
    spender: string;
    amount: string;
    approval: boolean | string;
  }

  router.post(
    '/approve',
    asyncHandler(
      async (
        req: Request<{}, {}, EthereumApproveRequest>,
        res: Response<EthereumApproveResponse | string, {}>
      ) => {
        const { spender, privateKey, token, amount } = req.body;
        let result;
        try {
          result = await approve(spender, privateKey, token, amount);
        } catch (err) {
          throw new HttpException(500, err.message);
        }
        return res.status(200).json(result);
      }
    )
  );

  interface EthereumPollRequest {
    txHash: string;
  }

  interface EthereumPollResponse {
    network: string;
    timestamp: number;
    latency: number;
    txHash: string;
    confirmed: boolean;
    receipt: providers.TransactionReceipt | null;
  }

  router.post(
    '/poll',
    asyncHandler(
      async (
        req: Request<{}, {}, EthereumPollRequest>,
        res: Response<EthereumPollResponse, {}>
      ) => {
        const initTime = Date.now();
        const receipt = await ethereum.getTransactionReceipt(req.body.txHash);
        const confirmed = receipt && receipt.blockNumber ? true : false;

        res.status(200).json({
          network: ConfigManager.config.ETHEREUM_CHAIN,
          timestamp: initTime,
          latency: latency(initTime, Date.now()),
          txHash: req.body.txHash,
          confirmed,
          receipt: receipt,
        });
      }
    )
  );
}
