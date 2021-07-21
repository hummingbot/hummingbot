import { AxiosInstance } from 'axios';
import { DefaultElements, MetaSysProps } from '../common-types';
export declare type UploadProps = {
    /**
     * System metadata
     */
    sys: MetaSysProps;
};
export interface Upload extends UploadProps, DefaultElements<UploadProps> {
    /**
     * Deletes this object on the server.
     * @return Promise for the deletion. It contains no data, but the Promise error case should be handled.
     * @example
     * const contentful = require('contentful-management')
     *
     * const client = contentful.createClient({
     *   accessToken: '<content_management_api_key>'
     * })
     *
     * client.getSpace('<space_id>')
     * .then((space) => space.getUpload('<upload_id>'))
     * .then((upload) => upload.delete())
     * .then((upload) => console.log(`upload ${upload.sys.id} updated.`))
     * .catch(console.error)
     */
    delete(): Promise<void>;
}
/**
 * @private
 * @param {Object} http - HTTP client instance
 * @param {Object} data - Raw upload data
 * @return {Upload} Wrapped upload data
 */
export declare function wrapUpload(http: AxiosInstance, data: UploadProps): {
    delete: () => Promise<void>;
} & UploadProps & {
    toPlainObject(): UploadProps;
};
