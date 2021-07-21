import { GraphQLSchema, InlineFragmentNode } from 'graphql';
import { Transform, Request } from '@graphql-tools/utils';
export default class AddFragmentsByField implements Transform {
    private readonly targetSchema;
    private readonly mapping;
    constructor(targetSchema: GraphQLSchema, mapping: Record<string, Record<string, InlineFragmentNode>>);
    transformRequest(originalRequest: Request): Request;
}
