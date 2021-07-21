import { GraphQLSchema, GraphQLOutputType } from 'graphql';
import { Transform, Request } from '@graphql-tools/utils';
export default class WrapConcreteTypes implements Transform {
    private readonly returnType;
    private readonly targetSchema;
    constructor(returnType: GraphQLOutputType, targetSchema: GraphQLSchema);
    transformRequest(originalRequest: Request): Request;
}
