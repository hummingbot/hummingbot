import { ParseOptions } from 'graphql';
import { GraphQLSchemaValidationOptions } from 'graphql/type/schema';
import { Source } from './loaders';
import { SchemaPrintOptions } from './types';
export declare function parseGraphQLJSON(location: string, jsonContent: string, options: SchemaPrintOptions & ParseOptions & GraphQLSchemaValidationOptions): Source;
