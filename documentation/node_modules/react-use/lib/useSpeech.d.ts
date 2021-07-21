export interface SpeechState {
    isPlaying: boolean;
    lang: string;
    voice: SpeechSynthesisVoice;
    rate: number;
    pitch: number;
    volume: number;
}
export interface SpeechOptions {
    lang?: string;
    voice?: SpeechSynthesisVoice;
    rate?: number;
    pitch?: number;
    volume?: number;
}
declare const useSpeech: (text: string, opts?: SpeechOptions) => SpeechState;
export default useSpeech;
