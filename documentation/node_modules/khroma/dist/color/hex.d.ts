import Channels from '../channels';
declare const Hex: {
    re: RegExp;
    parse: (color: string) => void | Channels;
    stringify: (channels: Channels) => string;
};
export default Hex;
