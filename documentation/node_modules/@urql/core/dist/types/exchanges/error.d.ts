import { Exchange, Operation } from '../types';
import { CombinedError } from '../utils';
export declare const errorExchange: ({ onError, }: {
    onError: (error: CombinedError, operation: Operation) => void;
}) => Exchange;
