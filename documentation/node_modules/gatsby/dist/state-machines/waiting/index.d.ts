import { MachineConfig } from "xstate";
import { IWaitingContext } from "./types";
export declare type WaitingResult = Pick<IWaitingContext, "nodeMutationBatch">;
/**
 * This idle state also handles batching of node mutations and running of
 * mutations when we first start it
 */
export declare const waitingStates: MachineConfig<IWaitingContext, any, any>;
export declare const waitingMachine: import("xstate").StateMachine<IWaitingContext, any, import("redux").AnyAction, {
    value: any;
    context: IWaitingContext;
}>;
