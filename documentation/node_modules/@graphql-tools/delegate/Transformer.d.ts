import { Request, ExecutionResult } from '@graphql-tools/utils';
import { DelegationContext, DelegationBinding } from './types';
export declare class Transformer {
    private transformations;
    private delegationContext;
    constructor(context: DelegationContext, binding?: DelegationBinding);
    private addTransform;
    transformRequest(originalRequest: Request): Request;
    transformResult(originalResult: ExecutionResult): ExecutionResult<Record<string, any>>;
}
