import { Span } from "opentracing";
import { ExecutionResultDataDefault } from "graphql/execution/execute";
import { Store } from "redux";
import { Reporter } from "../..";
import { ExecutionResult, Source } from "../../graphql";
import { IGatsbyState } from "../redux/types";
export declare type Runner = (query: string | Source, context: Record<string, any>) => Promise<ExecutionResult<ExecutionResultDataDefault>>;
export declare const createGraphQLRunner: (store: Store<IGatsbyState>, reporter: Reporter, { parentSpan, graphqlTracing, }?: {
    parentSpan: Span | undefined;
    graphqlTracing?: boolean | undefined;
}) => Runner;
