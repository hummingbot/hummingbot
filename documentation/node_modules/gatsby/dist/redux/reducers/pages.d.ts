import { IGatsbyState, IGatsbyPage, IDeleteCacheAction, ICreatePageAction, IDeletePageAction } from "../types";
export declare const pagesReducer: (state: Map<string, IGatsbyPage> | undefined, action: IDeleteCacheAction | ICreatePageAction | IDeletePageAction) => IGatsbyState["pages"];
