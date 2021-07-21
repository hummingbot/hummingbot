/// <reference types="node" />
import dns from 'dns';
import { Options as RetryOptions } from 'async-retry-ng';
export declare const localhostRegex: RegExp;
declare type Options = {
    ipv6?: boolean;
    minimumCacheTime?: number;
    refreshCache?: boolean;
    retryOpts?: RetryOptions;
    resolver?: typeof dns;
};
export default function dnsResolve(host: string, options?: Options): Promise<string>;
export declare function setupCache(): void;
export {};
