import { GraphQLSchema, DocumentNode } from 'graphql';
import { ITypeDefinitions, GraphQLParseOptions } from '@graphql-tools/utils';
export declare function buildSchemaFromTypeDefinitions(typeDefinitions: ITypeDefinitions, parseOptions?: GraphQLParseOptions): GraphQLSchema;
export declare function isDocumentNode(typeDefinitions: ITypeDefinitions): typeDefinitions is DocumentNode;
export declare function buildDocumentFromTypeDefinitions(typeDefinitions: ITypeDefinitions, parseOptions?: GraphQLParseOptions): DocumentNode;
