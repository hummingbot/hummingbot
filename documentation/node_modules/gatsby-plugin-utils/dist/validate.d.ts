import { ObjectSchema } from "./joi";
import { IPluginInfoOptions } from "./types";
interface IOptions {
    validateExternalRules?: boolean;
}
export declare function validateOptionsSchema(pluginSchema: ObjectSchema, pluginOptions: IPluginInfoOptions, options?: IOptions): Promise<IPluginInfoOptions>;
export {};
