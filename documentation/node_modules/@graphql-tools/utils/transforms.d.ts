import { GraphQLSchema } from 'graphql';
import { Request, Transform } from './Interfaces';
export declare function applySchemaTransforms(originalSchema: GraphQLSchema, transforms: Array<Transform>): GraphQLSchema;
export declare function applyRequestTransforms(originalRequest: Request, transforms: Array<Transform>): Request;
export declare function applyResultTransforms(originalResult: any, transforms: Array<Transform>): any;
