import { GraphQLSchema, GraphQLFieldConfig } from 'graphql';
import { Transform, Request } from '@graphql-tools/utils';
export default class RenameRootFields implements Transform {
    private readonly transformer;
    constructor(renamer: (operation: 'Query' | 'Mutation' | 'Subscription', name: string, fieldConfig: GraphQLFieldConfig<any, any>) => string);
    transformSchema(originalSchema: GraphQLSchema): GraphQLSchema;
    transformRequest(originalRequest: Request): Request;
}
