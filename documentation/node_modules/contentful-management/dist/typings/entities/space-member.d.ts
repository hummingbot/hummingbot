import { MetaSysProps, MetaLinkProps, DefaultElements } from '../common-types';
import { AxiosInstance } from 'axios';
export declare type SpaceMemberProps = {
    sys: MetaSysProps;
    /**
     * User is an admin
     */
    admin: boolean;
    /**
     * Array of Role Links
     */
    roles: MetaLinkProps[];
};
export interface SpaceMember extends SpaceMemberProps, DefaultElements<SpaceMemberProps> {
}
/**
 * @private
 * @param http - HTTP client instance
 * @param data - Raw space member data
 * @return Wrapped space member data
 */
export declare function wrapSpaceMember(http: AxiosInstance, data: SpaceMemberProps): SpaceMemberProps & {
    toPlainObject(): SpaceMemberProps;
};
/**
 * @private
 */
export declare const wrapSpaceMemberCollection: (http: AxiosInstance, data: import("../common-types").CollectionProp<SpaceMemberProps>) => import("../common-types").Collection<SpaceMemberProps & {
    toPlainObject(): SpaceMemberProps;
}, SpaceMemberProps>;
