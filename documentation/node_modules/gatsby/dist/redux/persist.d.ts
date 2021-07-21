import { ICachedReduxState } from "./types";
export declare function readFromCache(): ICachedReduxState;
export declare function writeToCache(contents: ICachedReduxState): void;
