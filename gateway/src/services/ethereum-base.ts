import { BigNumber, Contract, providers, Wallet } from 'ethers';
import abi from './ethereum.abi.json';
import axios from 'axios';
import fs from 'fs/promises';
import { TokenListType, TokenValue } from './base';

// information about an Ethereum token
export interface Token {
  chainID: number;
  address: string;
  name: string;
  symbol: string;
  decimals: number;
}

export class EthereumBase {
  private _provider;
  protected tokenList: Token[] = [];
  private tokenMap: Record<string, Token> = {};
  // there are async values set in the constructor
  private _ready: boolean = false;

  public chainID;
  public rpcUrl;
  public gasPriceConstant;
  public tokenListSource: string;
  public tokenListType: TokenListType;

  constructor(
    chainID: number,
    rpcUrl: string,
    tokenListSource: string,
    tokenListType: TokenListType,
    gasPriceConstant: number
  ) {
    this._provider = new providers.JsonRpcProvider(rpcUrl);
    this.chainID = chainID;
    this.rpcUrl = rpcUrl;
    this.gasPriceConstant = gasPriceConstant;
    this.tokenListSource = tokenListSource;
    this.tokenListType = tokenListType;
  }

  reload(
    chainID: number,
    rpcUrl: string,
    tokenListSource: string,
    tokenListType: TokenListType,
    gasPriceConstant: number
  ): void {
    this._ready = false;
    this._provider = new providers.JsonRpcProvider(rpcUrl);
    this.chainID = chainID;
    this.rpcUrl = rpcUrl;
    this.gasPriceConstant = gasPriceConstant;
    this.tokenListSource = tokenListSource;
    this.tokenListType = tokenListType;
  }

  ready(): boolean {
    return this._ready;
  }

  public get provider() {
    return this._provider;
  }

  async init(): Promise<void> {
    await this.loadTokens(this.tokenListSource, this.tokenListType);
    this._ready = true;
  }

  async loadTokens(
    tokenListSource: string,
    tokenListType: TokenListType
  ): Promise<void> {
    this.tokenList = await this.getTokenList(tokenListSource, tokenListType);
    this.tokenList.forEach(
      (token: Token) => (this.tokenMap[token.symbol] = token)
    );
  }

  // returns a Tokens for a given list source and list type
  async getTokenList(
    tokenListSource: string,
    tokenListType: TokenListType
  ): Promise<Token[]> {
    if (tokenListType === 'URL') {
      const { data } = await axios.get(tokenListSource);
      return data;
    } else {
      const { tokens } = JSON.parse(await fs.readFile(tokenListSource, 'utf8'));
      return tokens;
    }
  }

  // return the Token object for a symbol
  getTokenForSymbol(symbol: string): Token | null {
    return this.tokenMap[symbol] ? this.tokenMap[symbol] : null;
  }

  // returns the gas price.
  getGasPrice(): number {
    return this.gasPriceConstant;
  }

  // returns Wallet for a private key
  getWallet(privateKey: string): Wallet {
    return new Wallet(privateKey, this._provider);
  }

  // returns the ETH balance, convert BigNumber to string
  async getEthBalance(wallet: Wallet): Promise<TokenValue> {
    const balance = await wallet.getBalance();
    return { value: balance, decimals: 18 };
  }

  // returns the balance for an ERC-20 token
  async getERC20Balance(
    wallet: Wallet,
    tokenAddress: string,
    decimals: number
  ): Promise<TokenValue> {
    // instantiate a contract and pass in provider for read-only access
    const contract = new Contract(tokenAddress, abi.ERC20Abi, this._provider);
    const balance = await contract.balanceOf(wallet.address);
    return { value: balance, decimals: decimals };
  }

  // returns the allowance for an ERC-20 token
  async getERC20Allowance(
    wallet: Wallet,
    spender: string,
    tokenAddress: string,
    decimals: number
  ): Promise<TokenValue> {
    // instantiate a contract and pass in provider for read-only access
    const contract = new Contract(tokenAddress, abi.ERC20Abi, this._provider);
    const allowance = await contract.allowance(wallet.address, spender);
    return { value: allowance, decimals: decimals };
  }

  // returns an ethereum TransactionResponse for a txHash.
  async getTransaction(
    txHash: string
  ): Promise<providers.TransactionResponse | null> {
    return this._provider.getTransaction(txHash); // If it does makes sense shouldn't we be doing it here?
  }

  // returns an ethereum TransactionReceipt for a txHash if the transaction has been mined.
  async getTransactionReceipt(
    txHash: string
  ): Promise<providers.TransactionReceipt | null> {
    return this._provider.getTransactionReceipt(txHash);
  }

  // adds allowance by spender to transfer the given amount of Token
  async approveERC20(
    wallet: Wallet,
    spender: string,
    tokenAddress: string,
    amount: BigNumber
  ): Promise<boolean> {
    // instantiate a contract and pass in wallet, which act on behalf of that signer
    const contract = new Contract(tokenAddress, abi.ERC20Abi, wallet);
    return await contract.approve(spender, amount, {
      gasPrice: this.gasPriceConstant * 1e9,
      gasLimit: 100000,
    });
  }
}
