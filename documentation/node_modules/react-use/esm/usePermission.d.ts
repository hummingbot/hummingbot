declare type State = PermissionState | '';
declare const usePermission: (permissionDesc: DevicePermissionDescriptor | PermissionDescriptor | MidiPermissionDescriptor | PushPermissionDescriptor) => State;
export default usePermission;
