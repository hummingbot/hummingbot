import { GraphQLSchema } from 'graphql';
import { Transform, Request } from '@graphql-tools/utils';
export default class FilterToSchema implements Transform {
    private readonly targetSchema;
    constructor(targetSchema: GraphQLSchema);
    transformRequest(originalRequest: Request): Request;
}
