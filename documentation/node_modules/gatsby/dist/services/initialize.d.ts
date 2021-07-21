import { Store, AnyAction } from "redux";
import JestWorker from "jest-worker";
import { IGatsbyState } from "../redux/types";
import { IBuildContext } from "./types";
export declare function initialize({ program: args, parentSpan, }: IBuildContext): Promise<{
    store: Store<IGatsbyState, AnyAction>;
    workerPool: JestWorker;
}>;
