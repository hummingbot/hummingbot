import breakpoints from '../utils/breakpoints';
import styled from '@emotion/styled';

export default styled.div({
  padding: '40px 56px',
  [breakpoints.md]: {
    padding: '32px 48px'
  },
  [breakpoints.sm]: {
    padding: '24px 32px'
  }
});
