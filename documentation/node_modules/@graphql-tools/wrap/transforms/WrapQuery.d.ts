import { SelectionNode, SelectionSetNode } from 'graphql';
import { Transform, Request, ExecutionResult } from '@graphql-tools/utils';
export declare type QueryWrapper = (subtree: SelectionSetNode) => SelectionNode | SelectionSetNode;
export default class WrapQuery implements Transform {
    private readonly wrapper;
    private readonly extractor;
    private readonly path;
    constructor(path: Array<string>, wrapper: QueryWrapper, extractor: (result: any) => any);
    transformRequest(originalRequest: Request): Request;
    transformResult(originalResult: ExecutionResult): ExecutionResult;
}
