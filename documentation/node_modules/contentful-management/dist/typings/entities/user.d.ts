import { AxiosInstance } from 'axios';
import { DefaultElements, MetaSysProps } from '../common-types';
export declare type UserProps = {
    /**
     * System metadata
     */
    sys: MetaSysProps;
    /**
     * First name of the user
     */
    firstName: string;
    /**
     * Last name of the user
     */
    lastName: string;
    /**
     * Url to the users avatar
     */
    avatarUrl: string;
    /**
     * Email address of the user
     */
    email: string;
    /**
     * Activation flag
     */
    activated: boolean;
    /**
     * Number of sign ins
     */
    signInCount: number;
    /**
     * User confirmation flag
     */
    confirmed: boolean;
};
export interface User extends UserProps, DefaultElements<UserProps> {
}
/**
 * @private
 * @param http - HTTP client instance
 * @param data - Raw data
 * @return Normalized user
 */
export declare function wrapUser(http: AxiosInstance, data: UserProps): User;
/**
 * @private
 * @param http - HTTP client instance
 * @param data - Raw data collection
 * @return Normalized user collection
 */
export declare const wrapUserCollection: (http: AxiosInstance, data: import("../common-types").CollectionProp<UserProps>) => import("../common-types").Collection<User, UserProps>;
