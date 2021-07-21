import { AxiosInstance } from 'axios';
import { EntryFields } from './entry-fields';
import { DefaultElements, MetaSysProps } from '../common-types';
export declare type UIExtensionProps = {
    sys: MetaSysProps;
    extension: {
        /**
         * Extension name
         */
        name: string;
        /**
         * Field types where an extension can be used
         */
        fieldTypes: EntryFields[];
        /**
         * URL where the root HTML document of the extension can be found
         */
        src?: string;
        /**
         * String representation of the extension (e.g. inline HTML code)
         */
        srcdoc?: string;
        /**
         * Controls the location of the extension. If true it will be rendered on the sidebar instead of replacing the field's editing control
         */
        sidebar: boolean;
    };
};
export interface UIExtension extends UIExtensionProps, DefaultElements<UIExtensionProps> {
    /**
     * Sends an update to the server with any changes made to the object's properties
     * @return Object returned from the server with updated changes.
     * @example ```javascript
     * const contentful = require('contentful-management')
     *
     * const client = contentful.createClient({
     *   accessToken: '<content_management_api_key>'
     * })
     *
     * client.getSpace('<space_id>')
     * .then((space) => space.getUiExtension('<ui_extension_id>'))
     * .then((uiExtension) => {
     *   uiExtension.extension.name = 'New UI Extension name'
     *   return uiExtension.update()
     * })
     * .then((uiExtension) => console.log(`UI Extension ${uiExtension.sys.id} updated.`))
     * .catch(console.error)
     * ```
     */
    update(): Promise<UIExtension>;
    /**
     * Deletes this object on the server.
     * @return Promise for the deletion. It contains no data, but the Promise error case should be handled.
     * @example ```javascript
     * const contentful = require('contentful-management')
     *
     * const client = contentful.createClient({
     *   accessToken: '<content_management_api_key>'
     * })
     *
     * client.getSpace('<space_id>')
     * .then((space) => space.getUiExtension('<ui_extension_id>'))
     * .then((uiExtension) => uiExtension.delete())
     * .then(() => console.log(`UI Extension deleted.`))
     * .catch(console.error)
     * ```
     */
    delete(): Promise<void>;
}
/**
 * @private
 * @param http - HTTP client instance
 * @param data - Raw UI Extension data
 * @return Wrapped UI Extension data
 */
export declare function wrapUiExtension(http: AxiosInstance, data: UIExtensionProps): UIExtension;
/**
 * @private
 */
export declare const wrapUiExtensionCollection: (http: AxiosInstance, data: import("../common-types").CollectionProp<UIExtensionProps>) => import("../common-types").Collection<UIExtension, UIExtensionProps>;
