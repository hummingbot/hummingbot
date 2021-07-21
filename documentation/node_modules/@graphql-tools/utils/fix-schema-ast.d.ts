import { GraphQLSchema, BuildSchemaOptions } from 'graphql';
import { SchemaPrintOptions } from './types';
export declare function fixSchemaAst(schema: GraphQLSchema, options: BuildSchemaOptions & SchemaPrintOptions): GraphQLSchema;
