import { ActionsUnion, IGatsbyState } from "../types";
export declare const statusReducer: (state: {
    plugins: Record<string, import("../types").IGatsbyPlugin>;
    PLUGINS_HASH: string;
} | undefined, action: ActionsUnion) => IGatsbyState["status"];
