import { ListenerFn } from 'eventemitter3';
import { ExecutionResult } from 'graphql/execution/execute';
import { DocumentNode } from 'graphql/language/ast';
export interface Observer<T> {
    next?: (value: T) => void;
    error?: (error: Error) => void;
    complete?: () => void;
}
export interface Observable<T> {
    subscribe(observer: Observer<T>): {
        unsubscribe: () => void;
    };
}
export interface OperationOptions {
    query?: string | DocumentNode;
    variables?: Object;
    operationName?: string;
    [key: string]: any;
}
export declare type FormatedError = Error & {
    originalError?: any;
};
export interface Operation {
    options: OperationOptions;
    handler: (error: Error[], result?: any) => void;
}
export interface Operations {
    [id: string]: Operation;
}
export interface Middleware {
    applyMiddleware(options: OperationOptions, next: Function): void;
}
export declare type ConnectionParams = {
    [paramName: string]: any;
};
export declare type ConnectionParamsOptions = ConnectionParams | Function | Promise<ConnectionParams>;
export interface ClientOptions {
    connectionParams?: ConnectionParamsOptions;
    minTimeout?: number;
    timeout?: number;
    reconnect?: boolean;
    reconnectionAttempts?: number;
    connectionCallback?: (error: Error[], result?: any) => void;
    lazy?: boolean;
    inactivityTimeout?: number;
    wsOptionArguments?: any[];
}
export declare class SubscriptionClient {
    client: any;
    operations: Operations;
    private url;
    private nextOperationId;
    private connectionParams;
    private minWsTimeout;
    private wsTimeout;
    private unsentMessagesQueue;
    private reconnect;
    private reconnecting;
    private reconnectionAttempts;
    private backoff;
    private connectionCallback;
    private eventEmitter;
    private lazy;
    private inactivityTimeout;
    private inactivityTimeoutId;
    private closedByUser;
    private wsImpl;
    private wsProtocols;
    private wasKeepAliveReceived;
    private tryReconnectTimeoutId;
    private checkConnectionIntervalId;
    private maxConnectTimeoutId;
    private middlewares;
    private maxConnectTimeGenerator;
    private wsOptionArguments;
    constructor(url: string, options?: ClientOptions, webSocketImpl?: any, webSocketProtocols?: string | string[]);
    get status(): any;
    close(isForced?: boolean, closedByUser?: boolean): void;
    request(request: OperationOptions): Observable<ExecutionResult>;
    on(eventName: string, callback: ListenerFn, context?: any): Function;
    onConnected(callback: ListenerFn, context?: any): Function;
    onConnecting(callback: ListenerFn, context?: any): Function;
    onDisconnected(callback: ListenerFn, context?: any): Function;
    onReconnected(callback: ListenerFn, context?: any): Function;
    onReconnecting(callback: ListenerFn, context?: any): Function;
    onError(callback: ListenerFn, context?: any): Function;
    unsubscribeAll(): void;
    applyMiddlewares(options: OperationOptions): Promise<OperationOptions>;
    use(middlewares: Middleware[]): SubscriptionClient;
    private getConnectionParams;
    private executeOperation;
    private getObserver;
    private createMaxConnectTimeGenerator;
    private clearCheckConnectionInterval;
    private clearMaxConnectTimeout;
    private clearTryReconnectTimeout;
    private clearInactivityTimeout;
    private setInactivityTimeout;
    private checkOperationOptions;
    private buildMessage;
    private formatErrors;
    private sendMessage;
    private sendMessageRaw;
    private generateOperationId;
    private tryReconnect;
    private flushUnsentMessagesQueue;
    private checkConnection;
    private checkMaxConnectTimeout;
    private connect;
    private processReceivedData;
    private unsubscribe;
}
