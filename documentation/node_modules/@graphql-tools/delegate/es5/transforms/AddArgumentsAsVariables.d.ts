import { GraphQLSchema } from 'graphql';
import { Transform, Request } from '@graphql-tools/utils';
export default class AddArgumentsAsVariables implements Transform {
    private readonly targetSchema;
    private readonly args;
    constructor(targetSchema: GraphQLSchema, args: Record<string, any>);
    transformRequest(originalRequest: Request): Request;
}
