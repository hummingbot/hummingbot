/// <reference types="node" />
import { ExecFileSyncOptions } from 'child_process';
export declare function openssl(args: string[]): Buffer;
export declare function run(cmd: string, args: string[], options?: ExecFileSyncOptions): Buffer;
export declare function sudoAppend(file: string, input: ExecFileSyncOptions["input"]): void;
export declare function waitForUser(): Promise<{}>;
export declare function reportableError(message: string): Error;
export declare function mktmp(): string;
export declare function sudo(cmd: string): Promise<string | null>;
