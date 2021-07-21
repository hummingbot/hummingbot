import PropTypes from 'prop-types';
import React from 'react';
import breakpoints from '../utils/breakpoints';
import styled from '@emotion/styled';
import {IconArrowLeft} from '@apollo/space-kit/icons/IconArrowLeft';
import {IconArrowRight} from '@apollo/space-kit/icons/IconArrowRight';
import {Link} from 'gatsby';
import {colors} from '../utils/colors';
import {size} from 'polished';
import {smallCaps} from '../utils/typography';

const Container = styled.nav({
  display: 'flex',
  padding: '64px 0',
  [breakpoints.md]: {
    padding: '32px 0'
  }
});

const StyledLink = styled(Link)({
  display: 'flex',
  alignItems: 'center',
  color: 'inherit',
  textDecoration: 'none',
  svg: size(16),
  ':hover': {
    opacity: colors.hoverOpacity
  }
});

const LinkText = styled.div(({align = 'left'}) => {
  const marginProperty = `margin${align.charAt(0).toUpperCase() +
    align.slice(1)}`;
  return {
    [marginProperty]: 24,
    textAlign: align,
    [breakpoints.md]: {
      [marginProperty]: 16
    }
  };
});

const LinkHeading = styled.div(smallCaps, {
  fontSize: 12
});

const LinkTitle = styled.div({
  color: colors.text1
});

export default function PageNav(props) {
  return (
    <Container>
      {props.prevPage && (
        <StyledLink to={props.prevPage.path}>
          <IconArrowLeft />
          <LinkText>
            <LinkHeading>Previous</LinkHeading>
            <LinkTitle>{props.prevPage.title}</LinkTitle>
          </LinkText>
        </StyledLink>
      )}
      {props.nextPage && (
        <StyledLink to={props.nextPage.path} style={{marginLeft: 'auto'}}>
          <LinkText align="right">
            <LinkHeading>Next</LinkHeading>
            <LinkTitle>{props.nextPage.title}</LinkTitle>
          </LinkText>
          <IconArrowRight />
        </StyledLink>
      )}
    </Container>
  );
}

PageNav.propTypes = {
  prevPage: PropTypes.object,
  nextPage: PropTypes.object
};
