import { ExchangeIO, ExchangeInput } from '../types';
/** This is always the last exchange in the chain; No operation should ever reach it */
export declare const fallbackExchange: ({ dispatchDebug, }: Pick<ExchangeInput, 'dispatchDebug'>) => ExchangeIO;
export declare const fallbackExchangeIO: ExchangeIO;
