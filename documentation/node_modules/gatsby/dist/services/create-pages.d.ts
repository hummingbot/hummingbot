import { IDataLayerContext } from "../state-machines/data-layer/types";
export declare function createPages({ parentSpan, gatsbyNodeGraphQLFunction, store, deferNodeMutation, }: Partial<IDataLayerContext>): Promise<{
    deletedPages: Array<string>;
    changedPages: Array<string>;
}>;
