import { GraphQLList, GraphQLFieldConfig } from "graphql";
import { GatsbyResolver, IGatsbyConnection, IGatsbyResolverContext } from "./type-definitions";
export declare function findMany<TSource, TArgs>(typeName: string): GatsbyResolver<TSource, TArgs>;
export declare function findOne<TSource, TArgs>(typeName: string): GatsbyResolver<TSource, TArgs>;
declare type PaginatedArgs<TArgs> = TArgs & {
    skip?: number;
    limit?: number;
};
export declare function findManyPaginated<TSource, TArgs, TNodeType>(typeName: string): GatsbyResolver<TSource, PaginatedArgs<TArgs>>;
interface IFieldConnectionArgs {
    field: string;
}
export declare const distinct: GatsbyResolver<IGatsbyConnection<any>, IFieldConnectionArgs>;
export declare const group: GatsbyResolver<IGatsbyConnection<any>, PaginatedArgs<IFieldConnectionArgs>>;
export declare function paginate<NodeType>(results: NodeType[] | undefined, { skip, limit }: {
    skip?: number;
    limit?: number;
}): IGatsbyConnection<NodeType>;
export declare function link<TSource, TArgs>(options: {
    by: string;
    type?: import("graphql").GraphQLScalarType | import("graphql").GraphQLObjectType<any, any, {
        [key: string]: any;
    }> | import("graphql").GraphQLInterfaceType | import("graphql").GraphQLUnionType | import("graphql").GraphQLEnumType | import("graphql").GraphQLInputObjectType | GraphQLList<any> | import("graphql").GraphQLNonNull<any> | undefined;
    from?: string | undefined;
    fromNode?: string | undefined;
} | undefined, fieldConfig: GraphQLFieldConfig<TSource, IGatsbyResolverContext<TSource, TArgs>, TArgs>): GatsbyResolver<TSource, TArgs>;
export declare function fileByPath<TSource, TArgs>(options: {
    from?: string | undefined;
    fromNode?: string | undefined;
} | undefined, fieldConfig: any): GatsbyResolver<TSource, TArgs>;
export declare const defaultFieldResolver: GatsbyResolver<any, any>;
export declare function wrappingResolver<TSource, TArgs>(resolver: GatsbyResolver<TSource, TArgs>): GatsbyResolver<TSource, TArgs>;
export declare const defaultResolver: GatsbyResolver<any, any>;
export {};
