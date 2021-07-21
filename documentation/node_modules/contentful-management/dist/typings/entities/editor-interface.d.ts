import { AxiosInstance } from 'axios';
import { MetaSysProps, MetaLinkProps, DefaultElements } from '../common-types';
export interface Control {
    /**
     * the id of the customized field
     */
    fieldId: string;
    /**
     * customization associated to the field
     */
    widgetId: string;
    widgetNamespace: string;
}
export declare type EditorInterfaceProps = {
    sys: MetaSysProps & {
        space: {
            sys: MetaLinkProps;
        };
        environment: {
            sys: MetaLinkProps;
        };
        contentType: {
            sys: MetaLinkProps;
        };
    };
    /**
     * Array of fields and it's associated widgetId
     */
    controls: Control[];
};
export interface EditorInterface extends EditorInterfaceProps, DefaultElements<EditorInterfaceProps> {
    /**
     * Gets a control for a specific field
     * @return control object for specific field
     * ```javascript
     * const contentful = require('contentful-management')
     *
     * const client = contentful.createClient({
     *   accessToken: '<content_management_api_key>'
     * })
     *
     * client.getSpace('<space_id>')
     * .then((space) => space.getContentType('<contentType_id>'))
     * .then((contentType) => contentType.getEditorInterface())
     * .then((editorInterface) => {
     *  control = editorInterface.getControlForField('<field-id>')
     *  console.log(control)
     * })
     * .catch(console.error)
     * ```
     */
    getControlForField(id: string): null | Control;
    /**
     * Sends an update to the server with any changes made to the object's properties
     * @return Object returned from the server with updated changes.
     * ```javascript
     * const contentful = require('contentful-management')
     *
     * const client = contentful.createClient({
     *   accessToken: '<content_management_api_key>'
     * })
     *
     * client.getSpace('<space_id>')
     * .then((space) => space.getContentType('<contentType_id>'))
     * .then((contentType) => contentType.getEditorInterface())
     * .then((editorInterface) => {
     *  editorInterface.controls[0] = { "fieldId": "title", "widgetId": "singleLine"}
     *  return editorInterface.update()
     * })
     * .catch(console.error)
     * ```
     */
    update(): Promise<EditorInterface>;
}
/**
 * @private
 */
export declare function wrapEditorInterface(http: AxiosInstance, data: EditorInterfaceProps): EditorInterface;
