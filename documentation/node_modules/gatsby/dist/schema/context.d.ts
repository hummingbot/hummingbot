import { GraphQLSchema } from "graphql";
import { SchemaComposer } from "graphql-compose";
import { IGraphQLRunnerStats } from "../query/types";
import { IGatsbyResolverContext, IGraphQLSpanTracer } from "./type-definitions";
export default function withResolverContext<TSource, TArgs>({ schema, schemaComposer, context, customContext, nodeModel, stats, tracer, }: {
    schema: GraphQLSchema;
    schemaComposer: SchemaComposer<IGatsbyResolverContext<TSource, TArgs>> | null;
    context?: Record<string, any>;
    customContext?: Record<string, any>;
    nodeModel?: any;
    stats?: IGraphQLRunnerStats | null;
    tracer?: IGraphQLSpanTracer;
}): IGatsbyResolverContext<TSource, TArgs>;
