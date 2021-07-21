import { GraphQLSchema, GraphQLNamedType } from 'graphql';
import { Transform } from '@graphql-tools/utils';
export default class FilterTypes implements Transform {
    private readonly filter;
    constructor(filter: (type: GraphQLNamedType) => boolean);
    transformSchema(schema: GraphQLSchema): GraphQLSchema;
}
