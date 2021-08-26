import abi from '../../services/ethereum.abi.json';
import axios from 'axios';
import { logger } from '../../services/logger';
import { BigNumber, Contract, Wallet } from 'ethers';
import { EthereumBase, Token } from '../../services/ethereum-base';
import { ConfigManager } from '../../services/config-manager';
import { EthereumConfig } from './ethereum.config';
import { TokenValue } from '../../services/base';

// MKR does not match the ERC20 perfectly so we need to use a separate ABI.
const MKR_ADDRESS = '0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2';

export class Ethereum extends EthereumBase {
  private ethGasStationUrl: string;
  private gasPrice: number;
  private gasPriceLastUpdated: Date | null;

  constructor() {
    let config;
    if (ConfigManager.config.ETHEREUM_CHAIN === 'mainnet') {
      config = EthereumConfig.config.mainnet;
    } else {
      config = EthereumConfig.config.kovan;
    }

    super(
      config.chainId,
      config.rpcUrl + ConfigManager.config.INFURA_KEY,
      config.tokenListSource,
      config.tokenListType,
      ConfigManager.config.ETH_MANUAL_GAS_PRICE
    );

    this.ethGasStationUrl =
      'https://ethgasstation.info/api/ethgasAPI.json?api-key=' +
      ConfigManager.config.ETH_GAS_STATION_API_KEY;

    this.gasPrice = ConfigManager.config.ETH_MANUAL_GAS_PRICE;
    this.gasPriceLastUpdated = null;

    this.updateGasPrice();
  }

  // ethereum token lists are large. instead of reloading each time with
  // getTokenList, we can read the stored tokenList value from when the
  // object was initiated.
  getStoredTokenList(): Token[] {
    return this.tokenList;
  }

  // If ConfigManager.config.ETH_GAS_STATION_ENABLE is true this will
  // continually update the gas price.
  async updateGasPrice(): Promise<void> {
    if (ConfigManager.config.ETH_GAS_STATION_ENABLE) {
      const { data } = await axios.get(this.ethGasStationUrl);

      // divide by 10 to convert it to Gwei
      this.gasPrice = data[ConfigManager.config.ETH_GAS_STATION_GAS_LEVEL] / 10;
      this.gasPriceLastUpdated = new Date();

      setTimeout(
        this.updateGasPrice.bind(this),
        ConfigManager.config.ETH_GAS_STATION_REFRESH_TIME * 1000
      );
    }
  }

  getGasPrice(): number {
    return this.gasPrice;
  }

  // returns null if the gasPrice is manually set
  getGasPriceLastDated(): Date | null {
    return this.gasPriceLastUpdated;
  }

  // override getERC20Balance definition to handle MKR edge case
  async getERC20Balance(
    wallet: Wallet,
    tokenAddress: string,
    decimals: number
  ): Promise<TokenValue> {
    // instantiate a contract and pass in provider for read-only access
    const contract = this.getContract(tokenAddress);

    try {
      logger.info(
        'Requesting balance for owner ' +
          wallet.address +
          ' for token ' +
          tokenAddress +
          '.'
      );
      const balance = await contract.balanceOf(wallet.address);
      logger.info(balance);
      return { value: balance, decimals: decimals };
    } catch (err) {
      throw new Error(
        err.reason || `Error balance lookup for token address ${tokenAddress}`
      );
    }
  }

  // override getERC20Allowance
  async getERC20Allowance(
    wallet: Wallet,
    spender: string,
    tokenAddress: string,
    decimals: number
  ): Promise<TokenValue> {
    // instantiate a contract and pass in provider for read-only access
    const contract = this.getContract(tokenAddress);

    try {
      logger.info(
        'Requesting spender ' +
          spender +
          ' allowance for owner ' +
          wallet.address +
          ' for token ' +
          tokenAddress +
          '.'
      );
      const allowance = await contract.allowance(wallet.address, spender);
      logger.info(allowance);
      return { value: allowance, decimals: decimals };
    } catch (err) {
      throw new Error(err.reason || 'error allowance lookup');
    }
  }

  getContract(tokenAddress: string) {
    return tokenAddress === MKR_ADDRESS
      ? new Contract(tokenAddress, abi.MKRAbi, this.provider)
      : new Contract(tokenAddress, abi.ERC20Abi, this.provider);
  }

  // override approveERC20
  async approveERC20(
    wallet: Wallet,
    spender: string,
    tokenAddress: string,
    amount: BigNumber
  ): Promise<boolean> {
    try {
      // instantiate a contract and pass in wallet, which act on behalf of that signer
      const contract = this.getContract(tokenAddress);

      logger.info(
        'Calling approve method called for spender ' +
          spender +
          ' requesting allowance ' +
          amount.toString() +
          ' from owner ' +
          wallet.address +
          ' on token ' +
          tokenAddress +
          '.'
      );
      const response = await contract.approve(spender, amount, {
        gasPrice: this.gasPrice * 1e9,
        gasLimit: 100000,
      });
      logger.info(response);
      return response;
    } catch (err) {
      throw new Error(err.reason || 'error approval');
    }
  }

  getTokenBySymbol(tokenSymbol: string): Token | undefined {
    return this.tokenList.find(
      (token: Token) => token.symbol === tokenSymbol.toUpperCase()
    );
  }
}
