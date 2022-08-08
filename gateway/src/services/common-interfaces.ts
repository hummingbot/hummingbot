import {
  Contract,
  Transaction,
  Wallet,
  ContractInterface,
  BigNumber,
  ethers,
} from 'ethers';
import { EthereumBase } from './ethereum-base';
import { CosmosBase } from './cosmos-base';
import { Provider } from '@ethersproject/abstract-provider';
import { CurrencyAmount, Token, Trade } from '@uniswap/sdk';
import { Trade as UniswapV3Trade } from '@uniswap/v3-sdk';
import {
  TradeType,
  Currency,
  CurrencyAmount as UniswapCoreCurrencyAmount,
  Token as UniswapCoreToken,
} from '@uniswap/sdk-core';
import {
  Token as TokenPangolin,
  CurrencyAmount as CurrencyAmountPangolin,
  Trade as TradePangolin,
} from '@pangolindex/sdk';
import { Token as TokenCosmos } from './cosmos-base';
export interface ExpectedTrade {
  trade:
    | Trade
    | TradePangolin
    | UniswapV3Trade<Currency, UniswapCoreToken, TradeType>;
  expectedAmount:
    | CurrencyAmount
    | CurrencyAmountPangolin
    | UniswapCoreCurrencyAmount<Currency>;
}

export interface Uniswapish {
  router: string;
  routerAbi: ContractInterface;
  gasLimit: number;
  ttl: number;
  getTokenByAddress(address: string): Token | TokenPangolin | UniswapCoreToken;
  priceSwapIn(
    baseToken: Token | TokenPangolin | UniswapCoreToken,
    quoteToken: Token | TokenPangolin | UniswapCoreToken,
    amount: BigNumber
  ): Promise<ExpectedTrade | string>;
  priceSwapOut(
    quoteToken: Token | TokenPangolin | UniswapCoreToken,
    baseToken: Token | TokenPangolin | UniswapCoreToken,
    amount: BigNumber
  ): Promise<ExpectedTrade | string>;
  executeTrade(
    wallet: Wallet,
    trade:
      | Trade
      | TradePangolin
      | UniswapV3Trade<Currency, UniswapCoreToken, TradeType>,
    gasPrice: number,
    uniswapRouter: string,
    ttl: number,
    abi: ContractInterface,
    gasLimit: number,
    nonce?: number,
    maxFeePerGas?: BigNumber,
    maxPriorityFeePerGas?: BigNumber
  ): Promise<Transaction>;
}

export interface Ethereumish extends EthereumBase {
  cancelTx(wallet: Wallet, nonce: number): Promise<Transaction>;
  getSpender(reqSpender: string): string;
  getContract(
    tokenAddress: string,
    signerOrProvider?: Wallet | Provider
  ): Contract;
  gasPrice: number;
  nativeTokenSymbol: string;
  chain: string;
}
export interface Cosmosish extends CosmosBase {
  // cancelTx(wallet: Wallet, nonce: number): Promise<Transaction>;
  // getSpender(reqSpender: string): string;
  // getContract(
  //   tokenAddress: string,
  //   signerOrProvider?: Wallet | Provider
  // ): Contract;
  // gasPrice: number;
  // nativeTokenSymbol: string;
  chain: string;
}
export interface Sifchainish extends CosmosBase {
  // cancelTx(wallet: Wallet, nonce: number): Promise<Transaction>;
  // getSpender(reqSpender: string): string;
  // getContract(
  //   tokenAddress: string,
  //   signerOrProvider?: Wallet | Provider
  // ): Contract;
  // gasPrice: number;
  // nativeTokenSymbol: string;
  chain: string;
}

export interface SifchainishConnector {
  estimateSellTrade(
    baseToken: TokenCosmos,
    quoteToken: TokenCosmos,
    amount: string,
    allowedSlippage?: string
  ): Promise<ExpectedTrade | string>;
  estimateBuyTrade(
    quoteToken: TokenCosmos,
    baseToken: TokenCosmos,
    amount: string,
    allowedSlippage?: string
  ): Promise<ExpectedTrade | string>;
  chain: string;
}

export interface NetworkSelectionRequest {
  connector?: string; //the target connector (e.g. uniswap or pangolin)
  chain: string; //the target chain (e.g. ethereum, avalanche, or harmony)
  network: string; // the target network of the chain (e.g. mainnet)
}

export interface CustomTransactionReceipt
  extends Omit<
    ethers.providers.TransactionReceipt,
    'gasUsed' | 'cumulativeGasUsed' | 'effectiveGasPrice'
  > {
  gasUsed: string;
  cumulativeGasUsed: string;
  effectiveGasPrice: string | null;
}

export interface CustomTransaction
  extends Omit<
    Transaction,
    'maxPriorityFeePerGas' | 'maxFeePerGas' | 'gasLimit' | 'value'
  > {
  maxPriorityFeePerGas: string | null;
  maxFeePerGas: string | null;
  gasLimit: string | null;
  value: string;
}

export interface CustomTransactionResponse
  extends Omit<
    ethers.providers.TransactionResponse,
    'gasPrice' | 'gasLimit' | 'value'
  > {
  gasPrice: string | null;
  gasLimit: string;
  value: string;
}
