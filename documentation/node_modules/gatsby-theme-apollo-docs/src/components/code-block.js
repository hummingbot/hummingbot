import PropTypes from 'prop-types';
import React, {useRef} from 'react';
import styled from '@emotion/styled';
import useCopyToClipboard from 'react-use/lib/useCopyToClipboard';
import {Button} from '@apollo/space-kit/Button';
import {
  GA_EVENT_CATEGORY_CODE_BLOCK,
  MultiCodeBlockContext
} from './multi-code-block';
import {Select} from './select';
import {colors} from 'gatsby-theme-apollo-core';
import {trackCustomEvent} from 'gatsby-plugin-google-analytics';

const Container = styled.div({
  marginBottom: '1.45rem',
  border: `1px solid ${colors.divider}`,
  borderRadius: 4
});

const Header = styled.div({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'flex-end',
  padding: 10,
  borderBottom: `1px solid ${colors.divider}`
});

const StyledSelect = styled(Select)({
  marginRight: 8
});

const InnerContainer = styled.div({
  padding: 15,
  backgroundColor: colors.background,
  overflow: 'auto'
});

function CodeBlockHeader(props) {
  const [copied, copyToClipboard] = useCopyToClipboard();

  function handleCopy() {
    copyToClipboard(props.codeRef.current.innerText + '\n\n');
    trackCustomEvent({
      category: GA_EVENT_CATEGORY_CODE_BLOCK,
      action: 'Copy'
    });
  }

  return (
    <Header>
      <MultiCodeBlockContext.Consumer>
        {({languages, onLanguageChange, selectedLanguage}) =>
          languages && (
            <StyledSelect
              size="small"
              feel="flat"
              value={selectedLanguage}
              onChange={onLanguageChange}
              options={languages.reduce(
                (acc, {lang, label}) => ({
                  ...acc,
                  [lang]: label
                }),
                {}
              )}
            />
          )
        }
      </MultiCodeBlockContext.Consumer>
      <Button feel="flat" size="small" onClick={handleCopy}>
        {copied.value ? 'Copied!' : 'Copy'}
      </Button>
    </Header>
  );
}

CodeBlockHeader.propTypes = {
  codeRef: PropTypes.object.isRequired
};

export default function CodeBlock(props) {
  const codeRef = useRef();
  return (
    <Container>
      {!props.className.includes('language-text') && (
        <CodeBlockHeader codeRef={codeRef} />
      )}
      <InnerContainer>
        <pre ref={codeRef} {...props} />
      </InnerContainer>
    </Container>
  );
}

CodeBlock.propTypes = {
  className: PropTypes.string.isRequired
};
