import { MachineConfig } from "xstate";
import { IQueryRunningContext } from "./types";
export declare const queryStates: MachineConfig<IQueryRunningContext, any, any>;
export declare const queryRunningMachine: import("xstate").StateMachine<IQueryRunningContext, any, import("xstate").AnyEventObject, {
    value: any;
    context: IQueryRunningContext;
}>;
