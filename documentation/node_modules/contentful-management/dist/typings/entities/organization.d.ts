import { AxiosInstance } from 'axios';
import { ContentfulOrganizationAPI } from '../create-organization-api';
import { MetaSysProps, DefaultElements } from '../common-types';
export declare type Organization = DefaultElements<OrganizationProp> & OrganizationProp & ContentfulOrganizationAPI;
export declare type OrganizationProp = {
    /**
     * System metadata
     */
    sys: MetaSysProps;
    /**
     * Name
     */
    name: string;
};
/**
 * This method creates the API for the given organization with all the methods for
 * reading and creating other entities. It also passes down a clone of the
 * http client with an organization id, so the base path for requests now has the
 * organization id already set.
 * @private
 * @param http - HTTP client instance
 * @param data - API response for an Organization
 * @return {Organization}
 */
export declare function wrapOrganization(http: AxiosInstance, data: OrganizationProp): Organization;
/**
 * This method normalizes each organization in a collection.
 * @private
 */
export declare const wrapOrganizationCollection: (http: AxiosInstance, data: import("../common-types").CollectionProp<OrganizationProp>) => import("../common-types").Collection<Organization, OrganizationProp>;
