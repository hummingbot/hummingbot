import { IGatsbyState, ActionsUnion } from "./types";
export declare const emitter: import("../utils/mett").IMett;
export declare const readState: () => IGatsbyState;
export interface IMultiDispatch {
    <T extends ActionsUnion>(action: Array<T>): Array<T>;
}
export declare const configureStore: (initialState: IGatsbyState) => import("redux").Store<import("redux").CombinedState<IGatsbyState>, import("redux").AnyAction> & {
    dispatch: import("redux-thunk").ThunkDispatch<IGatsbyState, undefined, ActionsUnion> & IMultiDispatch;
};
export declare type GatsbyReduxStore = ReturnType<typeof configureStore>;
export declare const store: GatsbyReduxStore;
export declare const saveState: () => void;
