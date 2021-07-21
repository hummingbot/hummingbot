export declare type FilterFn = (rootValue?: any, args?: any, context?: any, info?: any) => boolean | Promise<boolean>;
export declare type ResolverFn = (rootValue?: any, args?: any, context?: any, info?: any) => AsyncIterator<any>;
export declare const withFilter: (asyncIteratorFn: ResolverFn, filterFn: FilterFn) => ResolverFn;
