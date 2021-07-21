import { GraphQLSchema, SelectionSetNode } from 'graphql';
import { Transform, Request } from '@graphql-tools/utils';
export default class AddSelectionSetsByType implements Transform {
    private readonly targetSchema;
    private readonly mapping;
    constructor(targetSchema: GraphQLSchema, mapping: Record<string, SelectionSetNode>);
    transformRequest(originalRequest: Request): Request;
}
