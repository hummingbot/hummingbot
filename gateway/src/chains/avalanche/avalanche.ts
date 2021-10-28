import abi from '../../services/ethereum.abi.json';
import { logger } from '../../services/logger';
import { BigNumber, Contract, Transaction, Wallet } from 'ethers';
import { EthereumBase } from '../../services/ethereum-base';
import { ConfigManager } from '../../services/config-manager';
import { AvalancheConfig } from './avalanche.config';
import { TokenValue } from '../../services/base';
import { Provider } from '@ethersproject/abstract-provider';
import { Ethereumish } from '../ethereum/ethereum';
import { PangolinConfig } from './pangolin/pangolin.config';

// MKR does not match the ERC20 perfectly so we need to use a separate ABI.
const MKR_ADDRESS = '0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2';

export class Avalanche extends EthereumBase implements Ethereumish {
  private static _instance: Avalanche;
  private _gasPrice: number;
  private _nativeTokenSymbol: string;
  // private _ethGasStationUrl: string;
  // private _gasPriceLastUpdated: Date | null;

  private constructor() {
    let config;
    switch (ConfigManager.config.AVALANCHE_CHAIN) {
      case 'fuji':
        config = AvalancheConfig.config.fuji;
        break;
      case 'avalanche':
        config = AvalancheConfig.config.avalanche;
        break;
      default:
        throw new Error('AVALANCHE_CHAIN not valid');
    }

    super(
      config.chainId,
      config.rpcUrl,
      config.tokenListSource,
      config.tokenListType,
      ConfigManager.config.AVAX_MANUAL_GAS_PRICE
    );
    this._nativeTokenSymbol = 'AVAX';
    this._gasPrice = ConfigManager.config.AVAX_MANUAL_GAS_PRICE;
    // this._ethGasStationUrl =
    //   'https://ethgasstation.info/api/ethgasAPI.json?api-key=' +
    //   ConfigManager.config.ETH_GAS_STATION_API_KEY;

    // this._gasPriceLastUpdated = null;

    // this.updateGasPrice();
  }

  public static getInstance(): Avalanche {
    if (!Avalanche._instance) {
      Avalanche._instance = new Avalanche();
    }

    return Avalanche._instance;
  }

  // getters

  public get gasPrice(): number {
    return this._gasPrice;
  }

  public get nativeTokenSymbol(): string {
    return this._nativeTokenSymbol;
  }

  // public get gasPriceLastDated(): Date | null {
  //   return this._gasPriceLastUpdated;
  // }

  // override getERC20Balance definition to handle MKR edge case
  async getERC20Balance(
    wallet: Wallet,
    tokenAddress: string,
    decimals: number
  ): Promise<TokenValue> {
    // instantiate a contract and pass in provider for read-only access
    const contract = this.getContract(tokenAddress, this.provider);

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
  }

  // override getERC20Allowance
  async getERC20Allowance(
    wallet: Wallet,
    spender: string,
    tokenAddress: string,
    decimals: number
  ): Promise<TokenValue> {
    // instantiate a contract and pass in provider for read-only access
    const contract = this.getContract(tokenAddress, this.provider);

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
  }

  getContract(tokenAddress: string, signerOrProvider?: Wallet | Provider) {
    return tokenAddress === MKR_ADDRESS
      ? new Contract(tokenAddress, abi.MKRAbi, signerOrProvider)
      : new Contract(tokenAddress, abi.ERC20Abi, signerOrProvider);
  }

  getSpender(reqSpender: string): string {
    let spender: string;
    if (reqSpender === 'pangolin') {
      if (ConfigManager.config.ETHEREUM_CHAIN === 'avalanche') {
        spender = PangolinConfig.config.avalanche.routerAddress;
      } else {
        spender = PangolinConfig.config.fuji.routerAddress;
      }
    } else {
      spender = reqSpender;
    }
    return spender;
  }

  // override approveERC20
  async approveERC20(
    wallet: Wallet,
    spender: string,
    tokenAddress: string,
    amount: BigNumber,
    nonce?: number
  ): Promise<Transaction> {
    // instantiate a contract and pass in wallet, which act on behalf of that signer
    const contract = this.getContract(tokenAddress, wallet);

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
    if (!nonce) {
      nonce = await this.nonceManager.getNonce(wallet.address);
    }
    const response = await contract.approve(spender, amount, {
      gasPrice: this._gasPrice * 1e9,
      gasLimit: 100000,
      nonce: nonce,
    });
    logger.info(response);

    await this.nonceManager.commitNonce(wallet.address, nonce);
    return response;
  }

  // cancel transaction
  async cancelTx(wallet: Wallet, nonce: number): Promise<Transaction> {
    logger.info(
      'Canceling any existing transaction(s) with nonce number ' + nonce + '.'
    );
    return super.cancelTx(wallet, nonce, this._gasPrice);
  }
}
