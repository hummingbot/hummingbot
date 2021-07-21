import { IconProceed } from "@apollo/space-kit/icons/IconProceed";
import styled from "@emotion/styled";
import { breakpoints, colors } from "gatsby-theme-apollo-core";
import React from "react";
import useSiteMetadata from "../../hooks/useSiteMetadata";
import "katex/dist/katex.min.css";

const Container = styled.div({
  display: "flex",
  flexShrink: 0,
  width: 240,
  [breakpoints.lg]: {
    width: "auto",
    marginRight: 0,
  },
  [breakpoints.md]: {
    display: "none",
  },
});

const StyledLink = styled.a({
  display: "flex",
  alignItems: "center",
  color: colors.primary,
  lineHeight: 2,
  textDecoration: "none",
  ":hover": {
    color: colors.primaryDark,
  },
});

const StyledIcon = styled(IconProceed)({
  height: "0.75em",
  marginLeft: "0.5em",
});

export default function HeaderButton() {
  const { headerButtonText, headerButtonLink } = useSiteMetadata();

  if (headerButtonText && headerButtonLink)
    return (
      <Container>
        <StyledLink
          href={headerButtonLink}
          target="_blank"
          rel="noopener noreferrer"
        >
          {headerButtonText}
          <StyledIcon weight="thin" />
        </StyledLink>
      </Container>
    );

  return null;
}
