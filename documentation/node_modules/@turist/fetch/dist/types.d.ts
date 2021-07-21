/// <reference types="node" />
import * as http from 'http';
import * as https from 'http';
import { Options as RetryOptions } from 'async-retry-ng';
import { Request, RequestInit, Response } from 'node-fetch';
import FetchRetryError from './fetch-retry-error';
export interface FetchOptions extends RequestInit {
    agent?: https.Agent | http.Agent;
    retry?: RetryOptions;
    onRedirect?: (res: Response, redirectOpts: FetchOptions) => void;
    onRetry?: (error: FetchRetryError, opts: FetchOptions) => void;
    body?: any;
}
export declare type Fetch = {
    (url: string | Request, options?: FetchOptions): Promise<Response>;
};
export declare type AgentOptions = http.AgentOptions | https.AgentOptions;
