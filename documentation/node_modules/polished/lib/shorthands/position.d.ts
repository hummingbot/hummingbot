import { Styles } from '../types/style';

declare function position(
  positionKeyword: string | null,
  ...values: Array<null | void | string | null | void | number>
): Styles;

export default position;
