/// <reference types="node" />
/**
 * Given a `require.resolve()` compatible path pointing to a JS module,
 * return an array listing the names of the module's exports.
 *
 * Returns [] for invalid paths and modules without exports.
 *
 * @param modulePath
 * @param mode
 * @param resolver
 */
export declare const resolveModuleExports: (modulePath: string, { mode, resolver }?: {
    mode?: string | undefined;
    resolver?: RequireResolve | undefined;
}) => Array<string>;
