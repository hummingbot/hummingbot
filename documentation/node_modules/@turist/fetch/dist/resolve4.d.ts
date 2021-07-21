/// <reference types="node" />
import dns, { RecordWithTtl } from 'dns';
export default function resolve4(host: string, resolver: typeof dns): Promise<RecordWithTtl[]>;
