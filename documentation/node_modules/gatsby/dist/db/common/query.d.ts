export interface IDbQueryQuery {
    type: "query";
    path: Array<string>;
    query: IDbFilterStatement;
}
export interface IDbQueryElemMatch {
    type: "elemMatch";
    path: Array<string>;
    nestedQuery: DbQuery;
}
export declare type DbQuery = IDbQueryQuery | IDbQueryElemMatch;
export declare enum DbComparator {
    EQ = "$eq",
    NE = "$ne",
    GT = "$gt",
    GTE = "$gte",
    LT = "$lt",
    LTE = "$lte",
    IN = "$in",
    NIN = "$nin",
    REGEX = "$regex",
    GLOB = "$glob"
}
declare type DbComparatorValue = string | number | boolean | RegExp | null;
export interface IDbFilterStatement {
    comparator: DbComparator;
    value: DbComparatorValue | Array<DbComparatorValue>;
}
/**
 * Converts a nested mongo args object into array of DbQuery objects,
 * structured representation of each distinct path of the query. We convert
 * nested objects with multiple keys to separate instances.
 */
export declare function createDbQueriesFromObject(filter: Record<string, any>): Array<DbQuery>;
export declare function prefixResolvedFields(queries: Array<DbQuery>, resolvedFields: object): Array<DbQuery>;
export declare function objectToDottedField(obj: object, path?: Array<string>): object;
export {};
