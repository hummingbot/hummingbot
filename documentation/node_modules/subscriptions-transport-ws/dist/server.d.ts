/// <reference types="node" />
import * as WebSocket from 'ws';
import { ExecutionResult, GraphQLSchema, DocumentNode, ValidationContext, GraphQLFieldResolver } from 'graphql';
import { IncomingMessage } from 'http';
export declare type ExecutionIterator = AsyncIterator<ExecutionResult>;
export interface ExecutionParams<TContext = any> {
    query: string | DocumentNode;
    variables: {
        [key: string]: any;
    };
    operationName: string;
    context: TContext;
    formatResponse?: Function;
    formatError?: Function;
    callback?: Function;
    schema?: GraphQLSchema;
}
export declare type ConnectionContext = {
    initPromise?: Promise<any>;
    isLegacy: boolean;
    socket: WebSocket;
    request: IncomingMessage;
    operations: {
        [opId: string]: ExecutionIterator;
    };
};
export interface OperationMessagePayload {
    [key: string]: any;
    query?: string;
    variables?: {
        [key: string]: any;
    };
    operationName?: string;
}
export interface OperationMessage {
    payload?: OperationMessagePayload;
    id?: string;
    type: string;
}
export declare type ExecuteFunction = (schema: GraphQLSchema, document: DocumentNode, rootValue?: any, contextValue?: any, variableValues?: {
    [key: string]: any;
}, operationName?: string, fieldResolver?: GraphQLFieldResolver<any, any>) => ExecutionResult | Promise<ExecutionResult> | AsyncIterator<ExecutionResult>;
export declare type SubscribeFunction = (schema: GraphQLSchema, document: DocumentNode, rootValue?: any, contextValue?: any, variableValues?: {
    [key: string]: any;
}, operationName?: string, fieldResolver?: GraphQLFieldResolver<any, any>, subscribeFieldResolver?: GraphQLFieldResolver<any, any>) => AsyncIterator<ExecutionResult> | Promise<AsyncIterator<ExecutionResult> | ExecutionResult>;
export interface ServerOptions {
    rootValue?: any;
    schema?: GraphQLSchema;
    execute?: ExecuteFunction;
    subscribe?: SubscribeFunction;
    validationRules?: Array<(context: ValidationContext) => any> | ReadonlyArray<any>;
    onOperation?: Function;
    onOperationComplete?: Function;
    onConnect?: Function;
    onDisconnect?: Function;
    keepAlive?: number;
}
export declare class SubscriptionServer {
    private onOperation;
    private onOperationComplete;
    private onConnect;
    private onDisconnect;
    private wsServer;
    private execute;
    private subscribe;
    private schema;
    private rootValue;
    private keepAlive;
    private closeHandler;
    private specifiedRules;
    static create(options: ServerOptions, socketOptionsOrServer: WebSocket.ServerOptions | WebSocket.Server): SubscriptionServer;
    constructor(options: ServerOptions, socketOptionsOrServer: WebSocket.ServerOptions | WebSocket.Server);
    get server(): WebSocket.Server;
    close(): void;
    private loadExecutor;
    private unsubscribe;
    private onClose;
    private onMessage;
    private sendKeepAlive;
    private sendMessage;
    private sendError;
}
