import { Span } from "opentracing";
import { DocumentNode, GraphQLSchema, Source, GraphQLError, ExecutionResult } from "graphql";
import { Store } from "redux";
import { IGatsbyState } from "../redux/types";
import { IGraphQLRunnerStatResults, IGraphQLRunnerStats } from "./types";
declare type Query = string | Source;
export interface IGraphQLRunnerOptions {
    collectStats?: boolean;
    graphqlTracing?: boolean;
}
export declare class GraphQLRunner {
    protected store: Store<IGatsbyState>;
    parseCache: Map<Query, DocumentNode>;
    nodeModel: any;
    schema: GraphQLSchema;
    validDocuments: WeakSet<DocumentNode>;
    scheduleClearCache: () => void;
    stats: IGraphQLRunnerStats | null;
    graphqlTracing: boolean;
    constructor(store: Store<IGatsbyState>, { collectStats, graphqlTracing }?: IGraphQLRunnerOptions);
    clearCache(): void;
    parse(query: Query): DocumentNode;
    validate(schema: GraphQLSchema, document: DocumentNode): ReadonlyArray<GraphQLError>;
    getStats(): IGraphQLRunnerStatResults | null;
    query(query: Query, context: Record<string, unknown>, { parentSpan, queryName, }: {
        parentSpan: Span | undefined;
        queryName: string;
    }): Promise<ExecutionResult>;
}
export {};
