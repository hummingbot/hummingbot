import { Exchange, ExchangeInput } from '../types';
/** This composes an array of Exchanges into a single ExchangeIO function */
export declare const composeExchanges: (exchanges: Exchange[]) => ({ client, forward, dispatchDebug, }: ExchangeInput) => import("../types").ExchangeIO;
