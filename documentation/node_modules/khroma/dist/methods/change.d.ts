import Channels from '../channels';
import { CHANNELS } from '../types';
declare function change(color: string | Channels, channels: Partial<CHANNELS>): string;
export default change;
