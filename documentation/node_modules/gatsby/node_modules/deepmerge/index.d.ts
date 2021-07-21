declare function deepmerge<T>(x: Partial<T>, y: Partial<T>, options?: deepmerge.Options): T;
declare function deepmerge<T1, T2>(x: Partial<T1>, y: Partial<T2>, options?: deepmerge.Options): T1 & T2;

declare namespace deepmerge {
	export interface Options {
		arrayMerge?(target: any[], source: any[], options?: Options): any[];
		clone?: boolean;
		isMergeableObject?(value: object): boolean;
	}

	export function all (objects: object[], options?: Options): object;
}

export = deepmerge;
