import PropTypes from 'prop-types';
import React, {useMemo, useRef, useState} from 'react';
import styled from '@emotion/styled';
import useClickAway from 'react-use/lib/useClickAway';
import {Button} from '@apollo/space-kit/Button';
import {IconArrowDown} from '@apollo/space-kit/icons/IconArrowDown';
import {colors} from 'gatsby-theme-apollo-core';
import {size} from 'polished';

const Wrapper = styled.div({
  position: 'relative'
});

const StyledIcon = styled(IconArrowDown)(size('1em'), {
  marginLeft: 12
});

const Menu = styled.div({
  minWidth: '100%',
  padding: 8,
  borderRadius: 4,
  boxShadow: [
    '0 3px 4px 0 rgba(18, 21, 26, 0.04)',
    '0 4px 8px 0 rgba(18, 21, 26, 0.08)',
    '0 0 0 1px rgba(18, 21, 26, 0.08)'
  ].toString(),
  backgroundColor: 'white',
  position: 'absolute',
  left: 0,
  top: '100%',
  zIndex: 1
});

const MenuItem = styled.button({
  width: '100%',
  padding: '1px 12px',
  fontSize: 13,
  lineHeight: 2,
  textAlign: 'left',
  border: 'none',
  borderRadius: 4,
  background: 'none',
  cursor: 'pointer',
  outline: 'none',
  ':hover': {
    backgroundColor: colors.background
  },
  '&.selected': {
    backgroundColor: colors.primary,
    color: 'white'
  }
});

const LabelWrapper = styled.div({
  position: 'relative'
});

const Spacer = styled.div({
  visibility: 'hidden'
});

const Label = styled.div({
  position: 'absolute',
  top: 0,
  left: 0
});

export function Select({className, style, options, value, onChange, ...props}) {
  const wrapperRef = useRef(null);
  const [open, setOpen] = useState(false);

  const optionKeys = useMemo(() => Object.keys(options), [options]);
  const labelHeight = useMemo(() => {
    switch (props.size) {
      case 'small':
        return 20;
      case 'large':
        return 27;
      default:
        return 22;
    }
  }, [props.size]);

  useClickAway(wrapperRef, () => {
    setOpen(false);
  });

  function handleClick() {
    setOpen(prevOpen => !prevOpen);
  }

  return (
    <Wrapper className={className} style={style} ref={wrapperRef}>
      <Button {...props} onClick={handleClick}>
        <LabelWrapper style={{height: labelHeight}}>
          {optionKeys.map(key => (
            <Spacer key={key}>{options[key]}</Spacer>
          ))}
          <Label>{options[value]}</Label>
        </LabelWrapper>
        <StyledIcon />
      </Button>
      {open && (
        <Menu>
          {optionKeys.map(key => {
            const text = options[key];
            return (
              <MenuItem
                key={key}
                onClick={() => {
                  onChange(key);
                  setOpen(false);
                }}
                className={key === value && 'selected'}
              >
                {text}
              </MenuItem>
            );
          })}
        </Menu>
      )}
    </Wrapper>
  );
}

Select.propTypes = {
  className: PropTypes.string,
  style: PropTypes.object,
  size: PropTypes.string,
  value: PropTypes.string.isRequired,
  options: PropTypes.object.isRequired,
  onChange: PropTypes.func.isRequired
};
