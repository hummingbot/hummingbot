import { AxiosInstance } from 'axios';
import { DefaultElements, MetaLinkProps, MetaSysProps, QueryOptions } from '../common-types';
export interface Options {
    teamId?: string;
    query?: QueryOptions;
}
export declare type TeamSpaceMembershipProps = {
    /**
     * System metadata
     */
    sys: MetaSysProps;
    /**
     * Is admin
     */
    admin: boolean;
    /**
     * Roles
     */
    roles: MetaLinkProps[];
};
export interface TeamSpaceMembership extends TeamSpaceMembershipProps, DefaultElements<TeamSpaceMembershipProps> {
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
     * .then((space) => space.getTeamSpaceMembership('<team_space_membership_id>'))
     * .then((teamSpaceMembership) => teamSpaceMembership.delete())
     * .then(() => console.log(`spaceMembership deleted.`))
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
     *
     * client.getSpace('<space_id>')
     *  .then((space) => space.getTeamSpaceMembership('team_space_membership_id'))
     *  .then((teamSpaceMembership) => {
     *    item.roles = [
     *      {
     *        sys: {
     *          type: 'Link',
     *          linkType: 'Role',
     *          id: 'role_id'
     *        }
     *      }
     *    ]
     *  })
     *  .then((spaceMembership) => console.log(`spaceMembership ${spaceMembership.sys.id} updated.`))
     *  .catch(console.error)
     *  ```
     */
    update(): Promise<TeamSpaceMembership>;
}
/**
 * @private
 * @param http - HTTP client instance
 * @param data - Raw space membership data
 * @return Wrapped team space membership data
 */
export declare function wrapTeamSpaceMembership(http: AxiosInstance, data: TeamSpaceMembershipProps): TeamSpaceMembership;
/**
 * @private
 */
export declare const wrapTeamSpaceMembershipCollection: (http: AxiosInstance, data: import("../common-types").CollectionProp<TeamSpaceMembershipProps>) => import("../common-types").Collection<TeamSpaceMembership, TeamSpaceMembershipProps>;
