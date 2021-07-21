export interface IAPIResponse {
    browser: Record<string, any>;
    node: Record<string, any>;
    ssr: Record<string, any>;
}
export declare const getLatestAPIs: () => Promise<IAPIResponse>;
