import { TYPE } from '../types';
declare class Type {
    type: TYPE;
    get(): TYPE;
    set(type: TYPE): void;
    reset(): void;
    is(type: TYPE): boolean;
}
export default Type;
