/**
 * Asynchronously get the MD5-sum of the file at `path`
 *
 * @returns a `Promise` that will be resolved with a string containing the MD5-sum
 */
declare function md5File (path: string): Promise<string>

/**
 * Synchronously get the MD5-sum of the file at `path`
 *
 * @returns a string containing the MD5-sum
 */
declare function md5FileSync (path: string): string

declare const module: (typeof md5File) & { sync: typeof md5FileSync }
export = module
