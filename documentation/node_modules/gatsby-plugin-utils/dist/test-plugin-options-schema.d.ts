import { GatsbyNode } from "gatsby";
import { IPluginInfoOptions } from "./types";
interface ITestPluginOptionsSchemaReturnType {
    errors: Array<string>;
    isValid: boolean;
}
export declare function testPluginOptionsSchema(pluginSchemaFunction: Exclude<GatsbyNode["pluginOptionsSchema"], undefined>, pluginOptions: IPluginInfoOptions): Promise<ITestPluginOptionsSchemaReturnType>;
export {};
