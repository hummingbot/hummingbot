import { CurveConfig } from './curve.config';
import {
    BigNumber,
    // Contract,
    ContractInterface,
    Transaction,
    Wallet,
  } from 'ethers';
import { percentRegexp } from '../../services/config-manager-v2';
import { ExpectedTrade, Tokenish, Uniswapish, UniswapishTrade } from '../../services/common-interfaces';
import { Ethereum } from '../../chains/ethereum/ethereum';
import curve from '@curvefi/api';


export class Curve implements Uniswapish {
    private static _instances: { [name: string]: Curve };
    private ethereum: Ethereum;
    private _chain: string;
    private _router: string;
    private _routerAbi: ContractInterface;
    private _gasLimit: number;
    private _ttl: number;
    private _ready: boolean = false;

    private constructor(chain: string, network: string) {
        this._chain = chain;
        const config = CurveConfig.config;
        this.ethereum = Ethereum.getInstance(network);
        this._ttl = config.ttl;
        // //TODO: Get the router ABI
        this._routerAbi = config.routerAddress(network);
        this._gasLimit = config.gasLimit;
        this._router = config.routerAddress(network);
      }
    // Remove when getting the configuration values.
    public ready(): boolean {
        return this._ready;
      }
      /**
       * Router address.
       */
      public get router(): string {
        return this._router;
      }
    
      /**
       * Router smart contract ABI.
       */
      public get routerAbi(): ContractInterface {
        return this._routerAbi;
      }
    
      /**
       * Default gas limit for swap transactions.
       */
      public get gasLimit(): number {
        return this._gasLimit;
      }
    
      /**
       * Default time-to-live for swap transactions, in seconds.
       */
      public get ttl(): number {
        return this._ttl;
      }

    public static getInstance(chain: string, network: string): Curve {
        if (Curve._instances === undefined) {
            Curve._instances = {};
        }
        if (!(chain + network in Curve._instances)) {
            Curve._instances[chain + network] = new Curve(chain, network);
        }
    
        return Curve._instances[chain + network];
      }

    async init(){
        if (this._chain == 'ethereum' && !this.ethereum.ready()){
            throw new Error('Ethereum is not available');
        }
        // // 1. Infura
        // curve.init("Infura", { network: this._network , apiKey: <INFURA_KEY> }, { chainId: 1 });
        
        // // 2. Web3 provider
        // curve.init('Web3', { externalProvider: <WEB3_PROVIDER> }, { chainId: 1 });

        this._ready= true;
    }
    getTokenByAddress(_address: string): Tokenish {
        throw new Error('Method not implemented.');
    }
    estimateSellTrade(_baseToken: Tokenish, _quoteToken: Tokenish, _amount: BigNumber): Promise<ExpectedTrade> {
        throw new Error('Method not implemented.');
    }
    estimateBuyTrade(_quoteToken: Tokenish, _baseToken: Tokenish, _amount: BigNumber): Promise<ExpectedTrade> {
        throw new Error('Method not implemented.');
    }
    executeTrade(_wallet: Wallet, _trade: UniswapishTrade, _gasPrice: number, _uniswapRouter: string, _ttl: number, _abi: ContractInterface, _gasLimit: number, _nonce?: number, _maxFeePerGas?: BigNumber, _maxPriorityFeePerGas?: BigNumber): Promise<Transaction> {
        throw new Error('Method not implemented.');
    }
}