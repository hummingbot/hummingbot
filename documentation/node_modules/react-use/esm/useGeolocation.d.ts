export interface GeoLocationSensorState {
    loading: boolean;
    accuracy: number | null;
    altitude: number | null;
    altitudeAccuracy: number | null;
    heading: number | null;
    latitude: number | null;
    longitude: number | null;
    speed: number | null;
    timestamp: number | null;
    error?: Error | PositionError;
}
declare const useGeolocation: (options?: PositionOptions | undefined) => GeoLocationSensorState;
export default useGeolocation;
