import {
    InitializationError,
    // UniswapishPriceError,
    SERVICE_UNITIALIZED_ERROR_CODE,
    SERVICE_UNITIALIZED_ERROR_MESSAGE,
} from '../../services/error-handler';
import { SushiswapConfig } from './sushiswap.config';
import routerAbi from './sushiswap_router.json';

import {
    // Contract,
    ContractInterface,
    // ContractTransaction,
} from '@ethersproject/contracts';

import {
    // Fetcher,
    // Percent,
    // Router,
    Token,
    // CurrencyAmount,
    // Trade,
    // Pair,
    // SwapParameters,
} from '@sushiswap/sdk'
import { ExpectedTrade, Tokenish, Uniswapish, UniswapishTrade } from '../../services/common-interfaces';
import { Ethereum } from '../../chains/ethereum/ethereum';
import { BigNumber, Wallet, Transaction } from 'ethers';

export class SushiSwap implements Uniswapish {
    private static _instances: { [name: string]: SushiSwap };
    private ethereum: Ethereum;
    private _chain: string;
    private _router: string;
    private _routerAbi: ContractInterface;
    private _gasLimit: number;
    private _ttl: number;
    private chainId;
    private tokenList: Record<string, Token> = {};
    private _ready: boolean = false;

    private constructor(chain: string, network: string) {
        this._chain = chain;
        const config = SushiswapConfig.config;
        this.ethereum = Ethereum.getInstance(network);
        this.chainId = this.ethereum.chainId;
        this._ttl = SushiswapConfig.config.ttl(2);
        this._routerAbi = routerAbi.abi;
        this._gasLimit = SushiswapConfig.config.gasLimit(2);
        this._router = config.sushiswapRouterAddress(network);
    }

    public static getInstance(chain: string, network: string): SushiSwap {
        if (SushiSwap._instances === undefined) {
            SushiSwap._instances = {};
        }
        if (!(chain + network in SushiSwap._instances)) {
            SushiSwap._instances[chain + network] = new SushiSwap(chain, network);
        }

        return SushiSwap._instances[chain + network];
    }


    public async init() {
        if (this._chain == 'ethereum' && !this.ethereum.ready())
            throw new InitializationError(
                SERVICE_UNITIALIZED_ERROR_MESSAGE('ETH'),
                SERVICE_UNITIALIZED_ERROR_CODE
            );
        for (const token of this.ethereum.storedTokenList) {
            this.tokenList[token.address] = new Token(
                this.chainId,
                token.address,
                token.decimals,
                token.symbol,
                token.name
            );
        }
        this._ready = true;
    }

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



    /**
     * Given a token's address, return the connector's native representation of
     * the token.
     *
     * @param address Token address
     */
    public getTokenByAddress(address: string): Token {
        return this.tokenList[address];
    }

    estimateSellTrade(_baseToken: Tokenish, _quoteToken: Tokenish, _amount: BigNumber): Promise<ExpectedTrade> {
        throw new Error('Method not implemented.');
    }
    estimateBuyTrade(_quoteToken: Tokenish, _baseToken: Tokenish, _amount: BigNumber): Promise<ExpectedTrade> {
        throw new Error('Method not implemented.');
    }
    executeTrade(_wallet: Wallet, _trade: UniswapishTrade, _gasPrice: number, _sushiswapRouter: string, _ttl: number, _abi: ContractInterface, _gasLimit: number, _nonce?: number, _maxFeePerGas?: BigNumber, _maxPriorityFeePerGas?: BigNumber): Promise<Transaction> {
        throw new Error('Method not implemented.');
    }


}