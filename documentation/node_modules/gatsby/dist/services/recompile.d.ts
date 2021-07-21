import { IBuildContext } from "./types";
import { Stats } from "webpack";
export declare function recompile({ webpackWatching, }: IBuildContext): Promise<Stats>;
