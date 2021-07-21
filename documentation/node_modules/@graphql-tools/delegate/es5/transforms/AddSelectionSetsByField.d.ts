import { GraphQLSchema, SelectionSetNode } from 'graphql';
import { Transform, Request } from '@graphql-tools/utils';
export default class AddSelectionSetsByField implements Transform {
    private readonly schema;
    private readonly mapping;
    constructor(schema: GraphQLSchema, mapping: Record<string, Record<string, SelectionSetNode>>);
    transformRequest(originalRequest: Request): Request;
}
