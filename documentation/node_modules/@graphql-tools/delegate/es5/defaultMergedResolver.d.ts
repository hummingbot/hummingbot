import { GraphQLResolveInfo } from 'graphql';
/**
 * Resolver that knows how to:
 * a) handle aliases for proxied schemas
 * b) handle errors from proxied schemas
 * c) handle external to internal enum coversion
 */
export declare function defaultMergedResolver(parent: Record<string, any>, args: Record<string, any>, context: Record<string, any>, info: GraphQLResolveInfo): any;
