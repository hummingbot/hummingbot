export type ErrorOverlayOptions = {
  /**
   * Path to a JS file that sets up the error overlay integration.
   */
  entry?: string | false;
  /**
   * The error overlay module to use.
   */
  module?: string | false;
  /**
   * The socket host to use (WDS only).
   */
  sockHost?: string;
  /**
   * Path to a JS file that sets up the Webpack socket integration.
   */
  sockIntegration?: import('type-fest').LiteralUnion<'wds' | 'whm' | 'wps' | false, string>;
  /**
   * The socket path to use (WDS only).
   */
  sockPath?: string;
  /**
   * The socket port to use (WDS only).
   */
  sockPort?: number;
  /**
   * Uses a custom SocketJS implementation for older versions of webpack-dev-server.
   */
  useLegacyWDSSockets?: boolean;
};
export type NormalizedErrorOverlayOptions = {
  /**
   * The socket host to use (WDS only).
   */
  sockHost?: string | undefined;
  /**
   * The socket path to use (WDS only).
   */
  sockPath?: string | undefined;
  /**
   * The socket port to use (WDS only).
   */
  sockPort?: number | undefined;
  /**
   * Uses a custom SocketJS implementation for older versions of webpack-dev-server.
   */
  useLegacyWDSSockets?: boolean | undefined;
  /**
   * The error overlay module to use.
   */
  module: string | false;
  /**
   * Path to a JS file that sets up the error overlay integration.
   */
  entry: string | false;
  /**
   * Path to a JS file that sets up the Webpack socket integration.
   */
  sockIntegration: import('type-fest').LiteralUnion<'wds' | 'whm' | 'wps' | false, string>;
};
export type ReactRefreshPluginOptions = {
  /**
   * Disables detection of react-refresh's Babel plugin (Deprecated since v0.3.0).
   */
  disableRefreshCheck?: boolean;
  /**
   * Files to explicitly exclude from processing.
   */
  exclude?: string | RegExp | Array<string | RegExp>;
  /**
   * Enables the plugin forcefully.
   */
  forceEnable?: boolean;
  /**
   * Files to explicitly include for processing.
   */
  include?: string | RegExp | Array<string | RegExp>;
  /**
   * Modifies how the error overlay integration works in the plugin.
   */
  overlay?: boolean | ErrorOverlayOptions;
};
export type OverlayOverrides = {
  /**
   * Modifies how the error overlay integration works in the plugin.
   */
  overlay: false | NormalizedErrorOverlayOptions;
};
export type NormalizedPluginOptions = Pick<
  {
    /**
     * Enables the plugin forcefully.
     */
    forceEnable?: boolean | undefined;
    /**
     * Files to explicitly include for processing.
     */
    include: string | RegExp | Array<string | RegExp>;
    /**
     * Files to explicitly exclude from processing.
     */
    exclude: string | RegExp | Array<string | RegExp>;
  },
  'include' | 'exclude' | 'forceEnable'
> &
  OverlayOverrides;
