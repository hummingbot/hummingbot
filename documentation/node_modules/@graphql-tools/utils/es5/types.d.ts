export interface SchemaPrintOptions {
    /**
     * Descriptions are defined as preceding string literals, however an older
     * experimental version of the SDL supported preceding comments as
     * descriptions. Set to true to enable this deprecated behavior.
     * This option is provided to ease adoption and will be removed in v16.
     *
     * Default: false
     */
    commentDescriptions?: boolean;
}
export declare type Maybe<T> = null | undefined | T;
export declare type Constructor<T> = new (...args: any[]) => T;
