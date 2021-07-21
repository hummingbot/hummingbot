export interface MiddlewareOptions {
    endpoint?: string;
    subscriptionEndpoint?: string;
    workspaceName?: string;
    env?: any;
    config?: any;
    settings?: ISettings;
    schema?: IntrospectionResult;
    tabs?: Tab[];
    codeTheme?: EditorColours;
}
export declare type CursorShape = 'line' | 'block' | 'underline';
export declare type Theme = 'dark' | 'light';
export interface ISettings {
    'general.betaUpdates': boolean;
    'editor.cursorShape': CursorShape;
    'editor.theme': Theme;
    'editor.reuseHeaders': boolean;
    'tracing.hideTracingResponse': boolean;
    'tracing.tracingSupported': boolean;
    'editor.fontSize': number;
    'editor.fontFamily': string;
    'request.credentials': string;
    'request.globalHeaders': {
        [key: string]: string;
    };
    'schema.polling.enable': boolean;
    'schema.polling.endpointFilter': string;
    'schema.polling.interval': number;
}
export interface EditorColours {
    property: string;
    comment: string;
    punctuation: string;
    keyword: string;
    def: string;
    qualifier: string;
    attribute: string;
    number: string;
    string: string;
    builtin: string;
    string2: string;
    variable: string;
    meta: string;
    atom: string;
    ws: string;
    selection: string;
    cursorColor: string;
    editorBackground: string;
    resultBackground: string;
    leftDrawerBackground: string;
    rightDrawerBackground: string;
}
export interface IntrospectionResult {
    __schema: any;
}
export interface RenderPageOptions extends MiddlewareOptions {
    version?: string;
    cdnUrl?: string;
    env?: any;
    title?: string;
    faviconUrl?: string | null;
}
export interface Tab {
    endpoint: string;
    query: string;
    name?: string;
    variables?: string;
    responses?: string[];
    headers?: {
        [key: string]: string;
    };
}
export declare function renderPlaygroundPage(options: RenderPageOptions): string;
