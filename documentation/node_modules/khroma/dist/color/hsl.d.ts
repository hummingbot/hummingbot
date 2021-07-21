import Channels from '../channels';
declare const HSL: {
    re: RegExp;
    hueRe: RegExp;
    _hue2deg(hue: string): number;
    parse: (color: string) => void | Channels;
    stringify: (channels: Channels) => string;
};
export default HSL;
