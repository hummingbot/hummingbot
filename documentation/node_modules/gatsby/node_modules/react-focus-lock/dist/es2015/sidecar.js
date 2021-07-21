import { exportSidecar } from 'use-sidecar';
import FocusTrap from './Trap';
import { mediumSidecar } from './medium';
export default exportSidecar(mediumSidecar, FocusTrap);