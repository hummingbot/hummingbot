import * as internalActions from "./internal";
import { actions as publicActions } from "./public";
import { actions as restrictedActions } from "./restricted";
export declare const actions: any;
export declare const boundActionCreators: any;
export declare const restrictedActionsAvailableInAPI: Record<string, {
    createFieldExtension: import("redux").ActionCreator<import("../types").ActionsUnion> | import("redux").ActionCreator<import("redux-thunk").ThunkAction<any, import("../types").IGatsbyState, any, import("../types").ActionsUnion>>;
    createTypes: import("redux").ActionCreator<import("../types").ActionsUnion> | import("redux").ActionCreator<import("redux-thunk").ThunkAction<any, import("../types").IGatsbyState, any, import("../types").ActionsUnion>>;
    createResolverContext: import("redux").ActionCreator<import("../types").ActionsUnion> | import("redux").ActionCreator<import("redux-thunk").ThunkAction<any, import("../types").IGatsbyState, any, import("../types").ActionsUnion>>;
    addThirdPartySchema: import("redux").ActionCreator<import("../types").ActionsUnion> | import("redux").ActionCreator<import("redux-thunk").ThunkAction<any, import("../types").IGatsbyState, any, import("../types").ActionsUnion>>;
    printTypeDefinitions: import("redux").ActionCreator<import("../types").ActionsUnion> | import("redux").ActionCreator<import("redux-thunk").ThunkAction<any, import("../types").IGatsbyState, any, import("../types").ActionsUnion>>;
}>;
export { internalActions, publicActions, restrictedActions };
