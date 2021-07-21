import { IGatsbyNode } from "./types";
import { IDbQueryElemMatch } from "../db/common/query";
export declare type FilterOp = "$eq" | "$ne" | "$lt" | "$lte" | "$gt" | "$gte" | "$in" | "$nin" | "$regex";
export declare type FilterValueNullable = string | number | boolean | null | undefined | RegExp | Array<string | number | boolean | null | undefined>;
declare type FilterValue = string | number | boolean | RegExp | Array<string | number | boolean>;
export declare type FilterCacheKey = string;
export interface IFilterCache {
    op: FilterOp;
    byValue: Map<FilterValueNullable, Array<IGatsbyNode>>;
    meta: {
        nodesUnordered?: Array<IGatsbyNode>;
        orderedByCounter?: Array<IGatsbyNode>;
        valuesAsc?: Array<FilterValue>;
        nodesByValueAsc?: Array<IGatsbyNode>;
        valueRangesAsc?: Map<FilterValue, [number, number]>;
        valuesDesc?: Array<FilterValue>;
        nodesByValueDesc?: Array<IGatsbyNode>;
        valueRangesDesc?: Map<FilterValue, [number, number]>;
    };
}
export declare type FiltersCache = Map<FilterCacheKey, IFilterCache>;
/**
 * Get all nodes from redux store.
 */
export declare const getNodes: () => Array<IGatsbyNode>;
/**
 * Get node by id from store.
 */
export declare const getNode: (id: string) => IGatsbyNode | undefined;
/**
 * Get all nodes of type from redux store.
 */
export declare const getNodesByType: (type: string) => Array<IGatsbyNode>;
/**
 * Get all type names from redux store.
 */
export declare const getTypes: () => Array<string>;
/**
 * Determine if node has changed.
 */
export declare const hasNodeChanged: (id: string, digest: string) => boolean;
/**
 * Get node and save path dependency.
 */
export declare const getNodeAndSavePathDependency: (id: string, path: string) => IGatsbyNode | undefined;
declare type Resolver = (node: IGatsbyNode) => Promise<any>;
export declare const saveResolvedNodes: (nodeTypeNames: Array<string>, resolver: Resolver) => Promise<void>;
/**
 * Get node and save path dependency.
 */
export declare const getResolvedNode: (typeName: string, id: string) => IGatsbyNode | null;
export declare function postIndexingMetaSetup(filterCache: IFilterCache, op: FilterOp): void;
/**
 * Given a single non-elemMatch filter path, a list of node types, and a
 * cache, create a cache that for each resulting value of the filter contains
 * all the Nodes in a list.
 * This cache is used for applying the filter and is a massive improvement over
 * looping over all the nodes, when the number of pages (/nodes) scales up.
 */
export declare const ensureIndexByQuery: (op: FilterOp, filterCacheKey: FilterCacheKey, filterPath: Array<string>, nodeTypeNames: Array<string>, filtersCache: FiltersCache) => void;
export declare function ensureEmptyFilterCache(filterCacheKey: any, nodeTypeNames: Array<string>, filtersCache: FiltersCache): void;
export declare const ensureIndexByElemMatch: (op: FilterOp, filterCacheKey: FilterCacheKey, filter: IDbQueryElemMatch, nodeTypeNames: Array<string>, filtersCache: FiltersCache) => void;
/**
 * Given the cache key for a filter and a target value return the list of nodes
 * that resolve to this value. The returned array should be ordered by id.
 * This returns `undefined` if there is no such node
 *
 * Basically if the filter was {a: {b: {slug: {eq: "foo/bar"}}}} then it will
 * return all the nodes that have `node.slug === "foo/bar"`. That usually (but
 * not always) at most one node for slug, but this filter can apply to anything.
 *
 * Arrays returned by this function must be ordered by internal.counter and
 * not contain duplicate nodes (!)
 */
export declare const getNodesFromCacheByValue: (filterCacheKey: FilterCacheKey, filterValue: FilterValueNullable, filtersCache: FiltersCache, wasElemMatch: any) => Array<IGatsbyNode> | undefined;
/**
 * Finds the intersection of two arrays in O(n) with n = min(a.length, b.length)
 * The returned set should not contain duplicate nodes.
 *
 * The input should be ordered by node.internal.counter and it will return a
 * list that is also ordered by node.internal.counter
 */
export declare function intersectNodesByCounter(a: Array<IGatsbyNode>, b: Array<IGatsbyNode>): Array<IGatsbyNode>;
/**
 * Merge two lists of nodes.
 * The returned set should not contain duplicate nodes.
 *
 * The input should be ordered by node.internal.counter and it will return a
 * list that is also ordered by node.internal.counter
 */
export declare function unionNodesByCounter(a: Array<IGatsbyNode>, b: Array<IGatsbyNode>): Array<IGatsbyNode>;
export {};
