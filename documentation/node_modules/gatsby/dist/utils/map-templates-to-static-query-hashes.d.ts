import { IGatsbyState } from "../redux/types";
import { Stats } from "webpack";
interface ICompilation {
    modules: Array<IModule>;
}
interface IReason extends Omit<Stats.Reason, "module"> {
    module: IModule;
}
interface IModule extends Omit<Stats.FnModules, "identifier" | "reasons"> {
    hasReasons: () => boolean;
    resource?: string;
    identifier: () => string;
    reasons: Array<IReason>;
}
export default function mapTemplatesToStaticQueryHashes(reduxState: IGatsbyState, compilation: ICompilation): Map<string, Array<number>>;
export {};
