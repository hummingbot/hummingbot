import { AxiosInstance } from 'axios';
import { ContentfulSpaceAPI } from '../create-space-api';
import { MetaSysProps, DefaultElements } from '../common-types';
export declare type SpaceProps = {
    sys: MetaSysProps;
    name: string;
};
export declare type Space = SpaceProps & DefaultElements<SpaceProps> & ContentfulSpaceAPI;
/**
 * This method creates the API for the given space with all the methods for
 * reading and creating other entities. It also passes down a clone of the
 * http client with a space id, so the base path for requests now has the
 * space id already set.
 * @private
 * @param http - HTTP client instance
 * @param data - API response for a Space
 * @return {Space}
 */
export declare function wrapSpace(http: AxiosInstance, data: SpaceProps): Space;
/**
 * This method wraps each space in a collection with the space API. See wrapSpace
 * above for more details.
 * @private
 */
export declare const wrapSpaceCollection: (http: AxiosInstance, data: import("../common-types").CollectionProp<SpaceProps>) => import("../common-types").Collection<Space, SpaceProps>;
