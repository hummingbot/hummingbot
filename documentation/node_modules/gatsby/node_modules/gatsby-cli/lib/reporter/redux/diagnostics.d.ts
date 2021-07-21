import { ActionsUnion } from "./types";
import type { GatsbyCLIStore } from "./";
declare type DiagnosticsMiddleware = (action: ActionsUnion) => void;
export declare function createStructuredLoggingDiagnosticsMiddleware(store: GatsbyCLIStore): DiagnosticsMiddleware;
export {};
