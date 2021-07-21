export interface ISiteMetadata {
    sitePath: string;
    name?: string;
    pid?: number;
    lastRun?: number;
}
export declare function getSiteMetadata(sitePath: string): Promise<ISiteMetadata | null>;
export declare function updateSiteMetadata(metadata: ISiteMetadata, merge?: boolean): Promise<void>;
