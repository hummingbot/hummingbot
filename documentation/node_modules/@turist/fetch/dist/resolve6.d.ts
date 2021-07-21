/// <reference types="node" />
import dns, { RecordWithTtl } from 'dns';
export default function resolve6(host: string, resolver: typeof dns): Promise<RecordWithTtl[]>;
