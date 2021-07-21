import { IDataLayerContext } from "./types";
export declare type DataLayerResult = Pick<IDataLayerContext, "gatsbyNodeGraphQLFunction" | "graphqlRunner" | "pagesToBuild" | "pagesToDelete">;
/**
 * Machine used during first run
 */
export declare const initializeDataMachine: import("xstate").StateMachine<IDataLayerContext, any, any, {
    value: any;
    context: IDataLayerContext;
}>;
/**
 * Machine used when we need to source nodes again
 */
export declare const reloadDataMachine: import("xstate").StateMachine<IDataLayerContext, any, any, {
    value: any;
    context: IDataLayerContext;
}>;
/**
 * Machine used when we need to re-create pages after a
 * node mutation outside of sourceNodes
 */
export declare const recreatePagesMachine: import("xstate").StateMachine<IDataLayerContext, any, any, {
    value: any;
    context: IDataLayerContext;
}>;
