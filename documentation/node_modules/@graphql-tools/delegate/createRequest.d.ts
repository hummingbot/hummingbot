import { GraphQLSchema, GraphQLObjectType, OperationTypeNode } from 'graphql';
import { Request } from '@graphql-tools/utils';
import { ICreateRequestFromInfo, ICreateRequest } from './types';
export declare function getDelegatingOperation(parentType: GraphQLObjectType, schema: GraphQLSchema): OperationTypeNode;
export declare function createRequestFromInfo({ info, operationName, operation, fieldName, selectionSet, fieldNodes, }: ICreateRequestFromInfo): Request;
export declare function createRequest({ sourceSchema, sourceParentType, sourceFieldName, fragments, variableDefinitions, variableValues, targetOperationName, targetOperation, targetFieldName, selectionSet, fieldNodes, }: ICreateRequest): Request;
