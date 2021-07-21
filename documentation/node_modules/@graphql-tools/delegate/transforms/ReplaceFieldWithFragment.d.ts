import { GraphQLSchema } from 'graphql';
import { Transform, Request } from '@graphql-tools/utils';
export default class ReplaceFieldWithFragment implements Transform {
    private readonly targetSchema;
    private readonly mapping;
    constructor(targetSchema: GraphQLSchema, fragments: Array<{
        field: string;
        fragment: string;
    }>);
    transformRequest(originalRequest: Request): Request;
}
