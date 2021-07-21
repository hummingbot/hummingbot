interface IRepositoryData {
    provider: string;
    owner?: string;
    name?: string;
}
export interface IRepositoryId {
    repositoryId: string;
    repositoryData?: IRepositoryData | null;
}
export declare const getRepoMetadata: (url: string) => IRepositoryData | null;
export declare const getRepositoryId: () => IRepositoryId;
export {};
