import { AxiosInstance } from 'axios';
import { MetaLinkProps, MetaSysProps, DefaultElements } from '../common-types';
export declare type ApiKeyProps = {
    sys: MetaSysProps;
    name: string;
    accessToken: string;
    environments: {
        sys: MetaLinkProps;
    }[];
    preview_api_key: {
        sys: MetaLinkProps;
    };
    description?: string;
    policies?: {
        effect: string;
        action: string;
    }[];
};
export declare type CreateApiKeyProps = Pick<ApiKeyProps, 'name' | 'environments' | 'description'>;
export interface ApiKey extends ApiKeyProps, DefaultElements<ApiKeyProps> {
    /**
     * Deletes this object on the server.
     * @return Promise for the deletion. It contains no data, but the Promise error case should be handled.
     * @example ```javascript
     * const contentful = require('contentful-management')
     *
     * const client = contentful.createClient({
     *   accessToken: '<content_management_api_key>'
     * })
     * client.getSpace('<space_id>')
     * .then((space) => space.getApiKey(<api-key-id>))
     * .then((apiKey) => apiKey.delete())
     * .then(() => console.log('apikey deleted'))
     * .catch(console.error)
     * ```
     */
    delete(): Promise<void>;
    /**
     * Sends an update to the server with any changes made to the object's properties
     * @return Object returned from the server with updated changes.
     * @example ```javascript
     * const contentful = require('contentful-management')
     *
     * const client = contentful.createClient({
     *   accessToken: '<content_management_api_key>'
     * })
     * client.getSpace('<space_id>')
     * .then((space) => space.getApiKey(<api-key-id>))
     * .then((apiKey) => {
     *  apiKey.name = 'New name'
     *  return apiKey.update()
     * })
     * .then(apiKey => console.log(apiKey.name))
     * .catch(console.error)
     * ```
     */
    update(): Promise<ApiKey>;
}
/**
 * @private
 * @param http - HTTP client instance
 * @param data - Raw api key data
 */
export declare function wrapApiKey(http: AxiosInstance, data: ApiKeyProps): ApiKey;
/**
 * @private
 * @param http - HTTP client instance
 * @param data - Raw api key collection data
 * @return Wrapped api key collection data
 */
export declare const wrapApiKeyCollection: (http: AxiosInstance, data: import("../common-types").CollectionProp<ApiKeyProps>) => import("../common-types").Collection<ApiKey, ApiKeyProps>;
