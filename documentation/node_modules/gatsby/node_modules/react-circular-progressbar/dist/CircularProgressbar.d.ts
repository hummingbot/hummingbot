import * as React from 'react';
import { CircularProgressbarDefaultProps, CircularProgressbarProps } from './types';
declare class CircularProgressbar extends React.Component<CircularProgressbarProps> {
    static defaultProps: CircularProgressbarDefaultProps;
    getBackgroundPadding(): number;
    getPathRadius(): number;
    getPathRatio(): number;
    render(): JSX.Element;
}
export default CircularProgressbar;
