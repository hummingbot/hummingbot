import { IGatsbyState, ActionsUnion } from "../types";
export declare const componentsReducer: (state: Map<string, {
    componentPath: string;
    query: string;
    pages: Set<string>;
    isInBootstrap: boolean;
}> | undefined, action: ActionsUnion) => IGatsbyState["components"];
