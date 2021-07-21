import Channels from '../channels';
declare const RGB: {
    re: RegExp;
    parse: (color: string) => void | Channels;
    stringify: (channels: Channels) => string;
};
export default RGB;
