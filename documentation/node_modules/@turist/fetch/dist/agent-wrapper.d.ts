/// <reference types="node" />
import * as http from 'http';
import { AgentOptions } from './types';
export default class Agent {
    #private;
    constructor(agentOpts: AgentOptions);
    getAgent(url: string): http.Agent;
}
