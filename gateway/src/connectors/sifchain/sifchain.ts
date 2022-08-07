import { percentRegexp } from '../../services/config-manager-v2';
// import {
//   BigNumber,
//   Contract,
//   ContractInterface,
//   Transaction,
//   Wallet,
// } from 'ethers';
import { SifchainConnectorConfig } from './sifchain.config';
// import routerAbi from './IPangolinRouter.json';
import {
  Percent,
  // Router,
  Token,
  // TokenAmount,
  // Trade,
} from '@pangolindex/sdk';
const { Decimal } = require('@cosmjs/math');
// import { logger } from '../../services/logger';
import {
  ExpectedTrade,
  SifchainishConnector,
} from '../../services/common-interfaces';
import { Sifchain } from '../../chains/sifchain/sifchain';
import { Token as CosmosToken } from '../../services/cosmos-base';
import { BigNumber } from 'ethers/lib/ethers';
import { logger } from '../../services/logger';

export class SifchainConnector implements SifchainishConnector {
  private static _instances: { [name: string]: SifchainConnector };
  private sifchain: Sifchain;
  public chain: string;
  private _router: string;
  // private _routerAbi: ContractInterface;
  private _gasLimit: number;
  private _ttl: number;
  private tokenList: Record<string, CosmosToken> = {};
  private _ready: boolean = false;

  private constructor(chain: string, network: string) {
    this.chain = chain;
    const config = SifchainConnectorConfig.config;
    this.sifchain = Sifchain.getInstance(network);
    this._router = config.routerAddress(network);
    this._ttl = config.ttl;
    // this._routerAbi = routerAbi.abi;
    this._gasLimit = config.gasLimit;
  }

  public static getInstance(chain: string, network: string): SifchainConnector {
    if (SifchainConnector._instances === undefined) {
      SifchainConnector._instances = {};
    }
    if (!(chain + network in SifchainConnector._instances)) {
      SifchainConnector._instances[chain + network] = new SifchainConnector(
        chain,
        network
      );
    }

    return SifchainConnector._instances[chain + network];
  }

  public getTokenByAddress(address: string): CosmosToken {
    return this.tokenList[address];
  }

  public async init() {
    if (this.chain == 'sifchain' && !this.sifchain.ready())
      throw new Error('Sifchain is not available');
    for (const token of this.sifchain.storedTokenList) {
      this.tokenList[token.address] = {
        base: token.base,
        address: token.address,
        decimals: token.decimals,
        symbol: token.symbol,
        name: token.name,
      };
    }
    this._ready = true;
  }

  public ready(): boolean {
    return this._ready;
  }

  public get router(): string {
    return this._router;
  }

  public get ttl(): number {
    return this._ttl;
  }

  // public get routerAbi(): ContractInterface {
  //   return this._routerAbi;
  // }

  public get gasLimit(): number {
    return this._gasLimit;
  }

  getSlippagePercentage(): Percent {
    const allowedSlippage = SifchainConnectorConfig.config.allowedSlippage;
    const nd = allowedSlippage.match(percentRegexp);

    if (nd) return eval(nd[0]);
    throw new Error(
      'Encountered a malformed percent string in the config for ALLOWED_SLIPPAGE.'
    );
  }

  // get the expected amount of token out, for a given pair and a token amount in.
  // this only considers direct routes.
  async priceSwapIn(
    // SELL - 100 USDT
    tokenIn: Token, // ATOM
    tokenOut: Token, // ROWAN
    tokenInAmount: BigNumber
  ): Promise<ExpectedTrade | string> {
    logger.info(
      `Fetching pair data for ${tokenIn.address}-${tokenOut.address}.`
    );

    const signingClient = await this.sifchain._signingClient;

    const swap = await signingClient.simulateSwap(
      {
        denom: tokenIn.denom,
        amount: Decimal.fromUserInput(tokenInAmount, tokenIn.decimals.low)
          .atomics,
      },
      { denom: tokenOut.denom },
      this.getSlippagePercentage() // Slippage
    );

    console.log(tokenIn);
    console.log(tokenOut);
    // console.log(swap);

    const rawReceiving = swap.rawReceiving.toFloatApproximation();
    const minimumReceiving = swap.minimumReceiving.toFloatApproximation();
    const liquidityProviderFee =
      swap.liquidityProviderFee.toFloatApproximation();
    const priceImpact = swap.priceImpact;

    return {
      rawReceiving,
      minimumReceiving,
      liquidityProviderFee,
      priceImpact,
    };
  }

  async priceSwapOut(
    // BUY
    tokenIn: Token, // ROWAN
    tokenOut: Token, // ATOM
    tokenOutAmount: string // I want to buy 100 ATOM, how much ROWAN do I need?
  ): Promise<ExpectedTrade | string> {
    logger.info(
      `Fetching pair data for ${tokenIn.baseDenom}-${tokenOut.baseDenom}.`
    );

    const signingClient = await this.sifchain._signingClient;

    // TODO: response has wrong values - https://sifchain-dex.redstarling.com/#/swap?from=c1inch&to=cuma&slippage=1.0
    // USDT per ATOM price
    const usdtPerAtom = await signingClient.simulateSwap(
      {
        denom: tokenOut.denom,
        amount: Decimal.fromUserInput('1', tokenOut.decimals.low).atomics,
      },
      { denom: tokenIn.denom },
      this.getSlippagePercentage() // Slippage
    );

    console.log(usdtPerAtom);

    const atomPerRowan = await signingClient.simulateSwap(
      {
        denom: tokenIn.denom,
        amount: Decimal.fromUserInput('1', tokenIn.decimals.low).atomics,
      },
      { denom: tokenOut.denom },
      this.getSlippagePercentage() // Slippage
    );

    console.log(atomPerRowan.rawReceiving.toFloatApproximation());

    // const pricePerTokenIn = inchPrice.rawReceiving.toFloatApproximation();
    // const usdtPerAtomPrice = usdtPerAtom.rawReceiving.toFloatApproximation();

    // console.log(usdtPerAtomPrice);
    // console.log(
    //   (usdtPerAtomPrice / tokenOutAmount).toFixed(tokenOut.decimals.low) +
    //     ' ATOM for 10000 ROWAN'
    // );

    // 100/0.000626
    // amount that i need to buy (tokenOutAmount)/atomPerRowan
    // 159662,1021606584
    // BUY 100 atom, how much rowan do I need to buy 100 atoms?
    // SELL 100 atom, how much rowan do I get? +
    const swap = await signingClient.simulateSwap(
      {
        denom: tokenOut.denom,
        amount: Decimal.fromUserInput(tokenOutAmount, tokenOut.decimals.low)
          .atomics,
      },
      { denom: tokenIn.denom },
      this.getSlippagePercentage() // Slippage
    );

    console.log(swap);
    console.log(swap.rawReceiving.toFloatApproximation());
    console.log(swap.minimumReceiving.toFloatApproximation());
    console.log(swap.liquidityProviderFee.toFloatApproximation());

    return;
  }

  // // given a wallet and a Uniswap trade, try to execute it on the Avalanche block chain.
  // async executeTrade(
  //   wallet: Wallet,
  //   trade: Trade,
  //   gasPrice: number,
  //   pangolinRouter: string,
  //   ttl: number,
  //   abi: ContractInterface,
  //   gasLimit: number,
  //   nonce?: number,
  //   maxFeePerGas?: BigNumber,
  //   maxPriorityFeePerGas?: BigNumber
  // ): Promise<Transaction> {
  //   const result = Router.swapCallParameters(trade, {
  //     ttl,
  //     recipient: wallet.address,
  //     allowedSlippage: this.getSlippagePercentage(),
  //   });

  //   const contract = new Contract(pangolinRouter, abi, wallet);
  //   if (!nonce) {
  //     nonce = await this.avalanche.nonceManager.getNonce(wallet.address);
  //   }
  //   let tx;
  //   if (maxFeePerGas || maxPriorityFeePerGas) {
  //     tx = await contract[result.methodName](...result.args, {
  //       gasLimit: gasLimit,
  //       value: result.value,
  //       nonce: nonce,
  //       maxFeePerGas,
  //       maxPriorityFeePerGas,
  //     });
  //   } else {
  //     tx = await contract[result.methodName](...result.args, {
  //       gasPrice: gasPrice * 1e9,
  //       gasLimit: gasLimit,
  //       value: result.value,
  //       nonce: nonce,
  //     });
  //   }

  //   logger.info(tx);
  //   await this.avalanche.nonceManager.commitNonce(wallet.address, nonce);
  //   return tx;
  // }
}
