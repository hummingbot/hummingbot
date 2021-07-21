import { IGraphQLConfig, IGraphQLProject, IGraphQLProjects, IGraphQLProjectLegacy } from '../types';
export declare function flatten<T>(arr: T[]): T extends (infer A)[] ? A[] : T[];
export declare function isMultipleProjectConfig(config: IGraphQLConfig): config is IGraphQLProjects;
export declare function isSingleProjectConfig(config: IGraphQLConfig): config is IGraphQLProject;
export declare function isLegacyProjectConfig(config: IGraphQLConfig): config is IGraphQLProjectLegacy;
export declare type MiddlewareFn<T> = (input: T) => T;
export declare function useMiddleware<T>(fns: Array<MiddlewareFn<T>>): (input: T) => T;
//# sourceMappingURL=utils.d.ts.map