import { GraphQLResolveInfo, GraphQLFieldResolver } from 'graphql';
export declare function chainResolvers(resolvers: Array<GraphQLFieldResolver<any, any>>): (root: any, args: {
    [argName: string]: any;
}, ctx: any, info: GraphQLResolveInfo) => any;
