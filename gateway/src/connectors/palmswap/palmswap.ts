import {
  HttpException,
  InitializationError,
  LOAD_WALLET_ERROR_CODE,
  LOAD_WALLET_ERROR_MESSAGE,
  SERVICE_UNITIALIZED_ERROR_CODE,
  SERVICE_UNITIALIZED_ERROR_MESSAGE,
} from '../../services/error-handler';
import { isFractionString } from '../../services/validators';
import { Amms, PalmConfig } from './palmswap.config';
import { PositionSide } from '@perp/sdk-curie';
import { Token } from '@uniswap/sdk';
import { Big } from 'big.js';
import { BigNumber, Transaction, Wallet } from 'ethers';
import { logger } from '../../services/logger';
import { percentRegexp } from '../../services/config-manager-v2';
import { Perpish } from '../../services/common-interfaces';
import { BinanceSmartChain } from '../../chains/binance-smart-chain/binance-smart-chain';
import { PerpConfig } from '../perp/perp.config';
import { PerpPosition } from '../perp/perp';
import { Contract } from '@ethersproject/contracts';
import { formatUnits, parseUnits } from '@ethersproject/units';
import clearingHouseABI from './clearing_house_abi.json';
import clearingHouseViewerABI from './clearing_house_viewer_abi.json';
import insuranceFundABI from './insurance_fund_abi.json';
import ammABI from './amm_abi.json';
import { JsonRpcProvider, Provider } from '@ethersproject/providers';

const PnlCalcOption = {
  SPOT_PRICE: 0,
  TWAP: 1,
};

const Side = {
  BUY: 0,
  SELL: 1,
};

interface Markets {
  [key: string]: Contract;
}

export class Palmswap implements Perpish {
  private static _instances: { [name: string]: Palmswap };
  public gasLimit = 2000000;
  private amms: Amms;
  private bsc: BinanceSmartChain;
  private _address: string;
  private _clearingHouseAddress: string;
  private _clearingHouseViewerAddress: string;
  private _wallet?: Wallet;
  private _clearingHouse?: Contract;
  private _clearingHouseViewer?: Contract;
  private _insuranceFund?: Contract;
  private _chain: string;
  private _provider: Provider;
  private chainId;
  private tokenList: Record<string, Token> = {};
  private _markets: Markets = {};
  private _ready: boolean = false;

  private constructor(chain: string, network: string, address?: string) {
    this.amms = PalmConfig.config.amms(network);
    this._clearingHouseAddress = PalmConfig.config.clearingHouse(network);
    this._clearingHouseViewerAddress =
      PalmConfig.config.clearingHouseViewer(network);
    this._chain = chain;
    this.bsc = BinanceSmartChain.getInstance(network);
    this.chainId = this.bsc.chainId;
    this._address = address ? address : '';
    this._provider = new JsonRpcProvider(
      'https://data-seed-prebsc-1-s3.binance.org:8545'
    );
  }

  public static getInstance(
    chain: string,
    network: string,
    address?: string
  ): Palmswap {
    if (Palmswap._instances === undefined) {
      Palmswap._instances = {};
    }

    if (!(chain + network + address in Palmswap._instances)) {
      Palmswap._instances[chain + network + address] = new Palmswap(
        chain,
        network,
        address
      );
    }

    return Palmswap._instances[chain + network + address];
  }

  public async init() {
    if (this._chain == 'binance-smart-chain' && !this.bsc.ready())
      throw new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE('BinanceSmartChain'),
        SERVICE_UNITIALIZED_ERROR_CODE
      );
    for (const token of this.bsc.storedTokenList) {
      this.tokenList[token.address] = new Token(
        this.chainId,
        token.address,
        token.decimals,
        token.symbol,
        token.name
      );
    }

    if (this._address !== '') {
      try {
        this._wallet = await this.bsc.getWallet(this._address);
        this._clearingHouseViewer = new Contract(
          this._clearingHouseViewerAddress,
          clearingHouseViewerABI,
          this._wallet
        );
        this._clearingHouse = new Contract(
          this._clearingHouseAddress,
          clearingHouseABI,
          this._wallet
        );
        const insuranceFundAddress = await this._clearingHouse.insuranceFund();
        this._insuranceFund = new Contract(
          insuranceFundAddress,
          insuranceFundABI,
          this._wallet
        );
      } catch (err) {
        logger.error(`Wallet ${this._address} not available.`);
        throw new HttpException(
          500,
          LOAD_WALLET_ERROR_MESSAGE + err,
          LOAD_WALLET_ERROR_CODE
        );
      }
    }
    this._ready = true;
  }

  /**
   * Gets the allowed slippage percent from the optional parameter or the value
   * in the configuration.
   *
   * @param allowedSlippageStr (Optional) should be of the form '1/10'.
   */
  public getAllowedSlippage(allowedSlippageStr?: string): number {
    let allowedSlippage;
    if (allowedSlippageStr != null && isFractionString(allowedSlippageStr)) {
      allowedSlippage = allowedSlippageStr;
    } else allowedSlippage = PerpConfig.config.allowedSlippage;
    const nd = allowedSlippage.match(percentRegexp);
    if (nd) return Number(nd[1]) / Number(nd[2]);
    throw new Error(
      'Encountered a malformed percent string in the config for ALLOWED_SLIPPAGE.'
    );
  }

  availablePairs(): string[] {
    return Object.keys(this.amms);
  }

  async closePosition(tickerSymbol: string): Promise<Transaction> {
    const amm = this.amms[tickerSymbol];
    if (!this._clearingHouse) {
      throw new Error('ClearingHouse has not been initialized');
    }
    return await this._clearingHouse.closePosition(
      amm,
      { d: '0' },
      {
        gasLimit: this.gasLimit,
      }
    );
  }

  async getAccountValue(): Promise<Big> {
    if (!this._clearingHouseViewer) {
      throw new Error('ClearingHouseViewer has not been initialized');
    }
    if (!this._insuranceFund) {
      throw new Error('InsuranceFund has not been initialized');
    }
    let accountValue = new Big(0);

    const amms = await this._insuranceFund.getAllAmms();
    for (const amm of amms) {
      const freeCollateral = await this._clearingHouseViewer.getFreeCollateral(
        amm,
        this._address
      );
      accountValue = accountValue.add(freeCollateral.toString());
    }

    return accountValue.div(1e18);
  }

  async getPositions(tickerSymbol: string): Promise<PerpPosition | undefined> {
    const amm = this.amms[tickerSymbol];
    if (!this._clearingHouseViewer) {
      throw new Error('ClearingHouseViewer has not been initialized');
    }
    const position =
      await this._clearingHouseViewer.getPersonalPositionWithFundingPayment(
        amm,
        this._address
      );

    let positionAmt: string = '0',
      positionSide: string = '',
      unrealizedProfit: string = '0',
      leverage: string = '1',
      entryPrice: string = '0';
    const pendingFundingPayment: string = '0';
    if (position && tickerSymbol && !position.size.d.eq(0)) {
      if (position) {
        positionSide = position.size.d.gt(0)
          ? PositionSide.LONG
          : PositionSide.SHORT;
        unrealizedProfit = (
          await this._clearingHouseViewer.getUnrealizedPnl(
            amm,
            this._address,
            PnlCalcOption.TWAP
          )
        ).toString();
        leverage = position.openNotional.d.div(position.margin.d).toString();
        entryPrice = position.openNotional.d
          .div(position.size.d)
          .abs()
          .toString();
        positionAmt = position.size.d.abs().toString();
      }
    }
    return {
      positionAmt,
      positionSide,
      unrealizedProfit,
      leverage,
      entryPrice,
      tickerSymbol,
      pendingFundingPayment,
    };
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

  async isMarketActive(tickerSymbol: string): Promise<boolean> {
    const market = this.getMarket(tickerSymbol);
    return await market.open();
  }

  async openPosition(
    isLong: boolean,
    tickerSymbol: string,
    minBaseAmount: string,
    allowedSlippage?: string
  ): Promise<Transaction> {
    const amm = this.amms[tickerSymbol];
    if (!this._clearingHouse) {
      throw new Error('ClearingHouse has not been initialized');
    }
    const slippage = this.getAllowedSlippage(allowedSlippage);
    const leverage = '1';
    const baseAmount = parseUnits(minBaseAmount);
    const market = this.getMarket(tickerSymbol);
    const dir = isLong ? '1' : '0';
    const quoteAmount = await market.getOutputPrice(dir, {
      d: baseAmount.mul(BigNumber.from(leverage)),
    });

    const slippageAmount = baseAmount.div(100).mul(slippage * 100);
    return await this._clearingHouse.openPosition(
      amm,
      isLong ? Side.BUY : Side.SELL,
      quoteAmount,
      { d: parseUnits(leverage) },
      {
        d: isLong
          ? baseAmount.sub(slippageAmount)
          : baseAmount.add(slippageAmount),
      },
      {
        gasLimit: this.gasLimit,
      }
    );
  }

  async prices(
    tickerSymbol: string
  ): Promise<{ markPrice: Big; indexPrice: Big; indexTwapPrice: Big }> {
    const market = this.getMarket(tickerSymbol);
    const indexTwapPrice = await market.getUnderlyingTwapPrice(15 * 60);
    const indexPrice = await market.getUnderlyingPrice();
    const markPrice = await market.getSpotPrice();
    return {
      indexTwapPrice: new Big(formatUnits(indexTwapPrice.d)),
      indexPrice: new Big(formatUnits(indexPrice.d)),
      markPrice: new Big(formatUnits(markPrice.d)),
    };
  }

  ready(): boolean {
    return this._ready;
  }

  getMarket(tickerSymbol: string): Contract {
    const address = this.amms[tickerSymbol];
    if (!this._markets[address]) {
      this._markets[address] = new Contract(address, ammABI, this._provider);
    }
    return this._markets[address];
  }
}
