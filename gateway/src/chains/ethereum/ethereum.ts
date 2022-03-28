import abi from '../../services/ethereum.abi.json';
import axios from 'axios';
import { logger } from '../../services/logger';
import { BigNumber, Contract, Transaction, Wallet } from 'ethers';
import { EthereumBase } from '../../services/ethereum-base';
import { EthereumConfig, getEthereumConfig } from './ethereum.config';
import { Provider } from '@ethersproject/abstract-provider';
import { UniswapConfig } from '../../connectors/uniswap/uniswap.config';
import { Ethereumish } from '../../services/common-interfaces';

// MKR does not match the ERC20 perfectly so we need to use a separate ABI.
const MKR_ADDRESS = '0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2';

export class Ethereum extends EthereumBase implements Ethereumish {
  private static _instances: { [name: string]: Ethereum };
  private _ethGasStationUrl: string;
  private _gasPrice: number;
  private _gasPriceRefreshInterval: number | null;
  private _gasPriceLastUpdated: Date | null;
  private _nativeTokenSymbol: string;
  private _chain: string;
  private _requestCount: number;
  private _metricsLogInterval: number;

  private constructor(network: string) {
    const config = getEthereumConfig('ethereum', network);
    super(
      'ethereum',
      config.network.chainID,
      config.network.nodeURL + config.nodeAPIKey,
      config.network.tokenListSource,
      config.network.tokenListType,
      config.manualGasPrice
    );
    this._chain = network;
    this._nativeTokenSymbol = config.nativeCurrencySymbol;
    this._ethGasStationUrl =
      EthereumConfig.ethGasStationConfig.gasStationURL +
      EthereumConfig.ethGasStationConfig.APIKey;

    this._gasPrice = config.manualGasPrice;
    this._gasPriceRefreshInterval =
      config.network.gasPriceRefreshInterval !== undefined
        ? config.network.gasPriceRefreshInterval
        : null;
    this._gasPriceLastUpdated = null;

    this.updateGasPrice();

    this._requestCount = 0;
    this._metricsLogInterval = 300000; // 5 minutes

    this.onDebugMessage(this.requestCounter.bind(this));
    setInterval(this.metricLogger.bind(this), this.metricsLogInterval);
  }

  public static getInstance(network: string): Ethereum {
    if (Ethereum._instances === undefined) {
      Ethereum._instances = {};
    }
    if (!(network in Ethereum._instances)) {
      Ethereum._instances[network] = new Ethereum(network);
    }

    return Ethereum._instances[network];
  }

  public static getConnectedInstances(): { [name: string]: Ethereum } {
    return Ethereum._instances;
  }

  public requestCounter(msg: any): void {
    if (msg.action === 'request') this._requestCount += 1;
  }

  public metricLogger(): void {
    logger.info(
      this.requestCount +
        ' request(s) sent in last ' +
        this.metricsLogInterval / 1000 +
        ' seconds.'
    );
    this._requestCount = 0; // reset
  }

  // getters
  public get gasPrice(): number {
    return this._gasPrice;
  }

  public get chain(): string {
    return this._chain;
  }

  public get nativeTokenSymbol(): string {
    return this._nativeTokenSymbol;
  }

  public get gasPriceLastDated(): Date | null {
    return this._gasPriceLastUpdated;
  }

  public get requestCount(): number {
    return this._requestCount;
  }

  public get metricsLogInterval(): number {
    return this._metricsLogInterval;
  }

  /**
   * Automatically update the prevailing gas price on the network.
   *
   * If ethGasStationConfig.enable is true, and the network is mainnet, then
   * the gas price will be updated from ETH gas station.
   *
   * Otherwise, it'll obtain the prevailing gas price from the connected
   * ETH node.
   */
  async updateGasPrice(): Promise<void> {
    if (this._gasPriceRefreshInterval === null) {
      return;
    }

    if (
      EthereumConfig.ethGasStationConfig.enabled &&
      this._chain === 'mainnet'
    ) {
      const { data } = await axios.get(this._ethGasStationUrl);

      // divide by 10 to convert it to Gwei
      this._gasPrice = data[EthereumConfig.ethGasStationConfig.gasLevel] / 10;
    } else {
      this._gasPrice = await this.getGasPriceFromEthereumNode();
    }

    this._gasPriceLastUpdated = new Date();
    setTimeout(
      this.updateGasPrice.bind(this),
      this._gasPriceRefreshInterval * 1000
    );
  }

  /**
   * Get the base gas fee and the current max priority fee from the Ethereum
   * node, and add them together.
   */
  async getGasPriceFromEthereumNode(): Promise<number> {
    const baseFee: BigNumber = await this.provider.getGasPrice();
    const priorityFee: BigNumber = BigNumber.from(
      await this.provider.send('eth_maxPriorityFeePerGas', [])
    );
    return baseFee.add(priorityFee).toNumber() * 1e-9;
  }

  getContract(
    tokenAddress: string,
    signerOrProvider?: Wallet | Provider
  ): Contract {
    return tokenAddress === MKR_ADDRESS
      ? new Contract(tokenAddress, abi.MKRAbi, signerOrProvider)
      : new Contract(tokenAddress, abi.ERC20Abi, signerOrProvider);
  }

  getSpender(reqSpender: string): string {
    let spender: string;
    if (reqSpender === 'uniswap') {
      spender = UniswapConfig.config.uniswapV2RouterAddress(this._chain);
    } else {
      spender = reqSpender;
    }
    return spender;
  }

  // cancel transaction
  async cancelTx(wallet: Wallet, nonce: number): Promise<Transaction> {
    logger.info(
      'Canceling any existing transaction(s) with nonce number ' + nonce + '.'
    );
    return this.cancelTxWithGasPrice(wallet, nonce, this._gasPrice * 2);
  }
}
