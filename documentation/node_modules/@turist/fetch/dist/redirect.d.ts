import { Response } from 'node-fetch';
import AgentWrapper from './agent-wrapper';
import { FetchOptions } from './types';
export declare const isRedirect: (v: number) => boolean;
export declare function makeRedirectOpts(res: Response, opts: FetchOptions, agentWrapper: AgentWrapper): [string, FetchOptions];
