import { Headers } from 'node-fetch';
export default function parseHost(url: string, headers: Headers): Promise<string[]>;
