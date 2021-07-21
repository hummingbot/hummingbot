import { IPluginInfo, ISiteConfig } from "./types";
/**
 * @param pluginName
 * This can be a name of a local plugin, the name of a plugin located in
 * node_modules, or a Gatsby internal plugin. In the last case the pluginName
 * will be an absolute path.
 * @param rootDir
 * This is the project location, from which are found the plugins
 */
export declare function resolvePlugin(pluginName: string, rootDir: string | null): IPluginInfo;
export declare function loadPlugins(config?: ISiteConfig, rootDir?: string | null): Array<IPluginInfo>;
