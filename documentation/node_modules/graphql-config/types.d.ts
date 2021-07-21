import { DocumentPointer, SchemaPointer } from '@graphql-tools/utils';
export declare type PointerWithConfiguration<T = any> = {
    [key: string]: T;
};
/**
 * Configuration of each used extension
 */
export interface IExtensions {
    [name: string]: any;
}
/**
 * Multiple named projects
 */
export interface IGraphQLProjects {
    projects: {
        [name: string]: IGraphQLProject | IGraphQLProjectLegacy;
    };
}
/**
 * Structure of GraphQL Config
 */
export declare type IGraphQLConfig = IGraphQLProject | IGraphQLProjects | IGraphQLProjectLegacy;
/**
 * Legacy structure of GraphQL Config v2
 */
export interface IGraphQLProjectLegacy {
    schemaPath: string;
    includes?: string[];
    excludes?: string[];
    extensions?: {
        [name: string]: any;
    };
}
/**
 * GraphQL Project
 */
export interface IGraphQLProject {
    schema: SchemaPointer;
    documents?: DocumentPointer;
    extensions?: IExtensions;
    include?: string | string[];
    exclude?: string | string[];
}
export interface GraphQLConfigResult {
    config: IGraphQLConfig;
    filepath: string;
}
//# sourceMappingURL=types.d.ts.map