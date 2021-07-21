import { ActionsUnion, IGatsbyState, IGatsbyIncompleteJobV2, IGatsbyCompleteJobV2 } from "../types";
export declare const jobsV2Reducer: (state: {
    incomplete: Map<string, IGatsbyIncompleteJobV2>;
    complete: Map<string, IGatsbyCompleteJobV2>;
} | undefined, action: ActionsUnion) => IGatsbyState["jobsV2"];
