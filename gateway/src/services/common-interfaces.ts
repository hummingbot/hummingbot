import {
  Contract,
  Transaction,
  Wallet,
  ContractInterface,
  BigNumber,
  ethers,
} from 'ethers';
import { EthereumBase } from './ethereum-base';
import { Provider } from '@ethersproject/abstract-provider';
import { CurrencyAmount, Token, Trade } from '@uniswap/sdk';
import { Trade as UniswapV3Trade } from '@uniswap/v3-sdk';
import {
  TradeType,
  Currency,
  CurrencyAmount as UniswapCoreCurrencyAmount,
  Token as UniswapCoreToken,
  Fraction as UniswapFraction,
} from '@uniswap/sdk-core';
import {
  Token as TokenPangolin,
  CurrencyAmount as CurrencyAmountPangolin,
  Trade as TradePangolin,
  Fraction as PangolinFraction,
} from '@pangolindex/sdk';

export type Tokenish = Token | TokenPangolin | UniswapCoreToken;
export type UniswapishTrade =
  | Trade
  | TradePangolin
  | UniswapV3Trade<Currency, UniswapCoreToken, TradeType>;
export type UniswapishAmount =
  | CurrencyAmount
  | CurrencyAmountPangolin
  | UniswapCoreCurrencyAmount<Currency>;
export type Fractionish = UniswapFraction | PangolinFraction;

export interface ExpectedTrade {
  trade: UniswapishTrade;
  expectedAmount: UniswapishAmount;
}

export interface Uniswapish {
  /**
   * Router address.
   */
  router: string;

  /**
   * Router smart contract ABI.
   */
  routerAbi: ContractInterface;

  /**
   * Default gas limit for swap transactions.
   */
  gasLimit: number;

  /**
   * Default time-to-live for swap transactions, in seconds.
   */
  ttl: number;

  /**
   * Given a token's address, return the connector's native representation of
   * the token.
   *
   * @param address Token address
   */
  getTokenByAddress(address: string): Tokenish;

  /**
   * Given the amount of `baseToken` to put into a transaction, calculate the
   * amount of `quoteToken` that can be expected from the transaction.
   *
   * This is typically used for calculating token sell prices.
   *
   * @param baseToken Token input for the transaction
   * @param quoteToken Output from the transaction
   * @param amount Amount of `baseToken` to put into the transaction
   */
  estimateSellTrade(
    baseToken: Tokenish,
    quoteToken: Tokenish,
    amount: BigNumber
  ): Promise<ExpectedTrade>;

  /**
   * Given the amount of `baseToken` desired to acquire from a transaction,
   * calculate the amount of `quoteToken` needed for the transaction.
   *
   * This is typically used for calculating token buy prices.
   *
   * @param quoteToken Token input for the transaction
   * @param baseToken Token output from the transaction
   * @param amount Amount of `baseToken` desired from the transaction
   */
  estimateBuyTrade(
    quoteToken: Tokenish,
    baseToken: Tokenish,
    amount: BigNumber
  ): Promise<ExpectedTrade>;

  /**
   * Given a wallet and a Uniswap-ish trade, try to execute it on blockchain.
   *
   * @param wallet Wallet
   * @param trade Expected trade
   * @param gasPrice Base gas price, for pre-EIP1559 transactions
   * @param uniswapRouter Router smart contract address
   * @param ttl How long the swap is valid before expiry, in seconds
   * @param abi Router contract ABI
   * @param gasLimit Gas limit
   * @param nonce (Optional) EVM transaction nonce
   * @param maxFeePerGas (Optional) Maximum total fee per gas you want to pay
   * @param maxPriorityFeePerGas (Optional) Maximum tip per gas you want to pay
   */
  executeTrade(
    wallet: Wallet,
    trade: UniswapishTrade,
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
