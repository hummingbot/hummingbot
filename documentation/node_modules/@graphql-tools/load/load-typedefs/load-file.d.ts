import { Source } from '@graphql-tools/utils';
import { LoadTypedefsOptions } from '../load-typedefs';
export declare function loadFile(pointer: string, options: LoadTypedefsOptions): Promise<Source>;
export declare function loadFileSync(pointer: string, options: LoadTypedefsOptions): Source;
