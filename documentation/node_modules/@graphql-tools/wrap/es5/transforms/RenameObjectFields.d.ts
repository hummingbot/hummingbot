import { GraphQLSchema, GraphQLFieldConfig } from 'graphql';
import { Transform, Request } from '@graphql-tools/utils';
export default class RenameObjectFields implements Transform {
    private readonly transformer;
    constructor(renamer: (typeName: string, fieldName: string, fieldConfig: GraphQLFieldConfig<any, any>) => string);
    transformSchema(originalSchema: GraphQLSchema): GraphQLSchema;
    transformRequest(originalRequest: Request): Request;
}
