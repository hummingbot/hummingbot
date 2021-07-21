import * as CSS from 'csstype';
import {Atoms} from '../addon/atoms';

export interface CssProps extends CSS.Properties, CSS.PropertiesHyphen, Atoms {}

export interface CssLikeObject extends CssProps {
    [selector: string]: any | CssLikeObject;
}

export type TDynamicCss = (css: CssLikeObject) => string;
export type THyperstyleElement = object;
export type THyperstyle = (...args) => THyperstyleElement;
export type THyperscriptType = string | Function;
export type THyperscriptComponent = Function;
