import { GraphQLSchema } from 'graphql';
import { Transform, RootFieldFilter } from '@graphql-tools/utils';
export default class FilterRootFields implements Transform {
    private readonly transformer;
    constructor(filter: RootFieldFilter);
    transformSchema(originalSchema: GraphQLSchema): GraphQLSchema;
}
