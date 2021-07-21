import PropTypes from 'prop-types';
import React, {createContext, useContext, useMemo} from 'react';
import styled from '@emotion/styled';
import {trackCustomEvent} from 'gatsby-plugin-google-analytics';

export const GA_EVENT_CATEGORY_CODE_BLOCK = 'Code Block';
export const MultiCodeBlockContext = createContext({});
export const SelectedLanguageContext = createContext();

const Container = styled.div({
  position: 'relative'
});

const langLabels = {
  js: 'JavaScript',
  ts: 'TypeScript',
  'hooks-js': 'Hooks (JS)',
  'hooks-ts': 'Hooks (TS)'
};

function getUnifiedLang(language) {
  switch (language) {
    case 'js':
    case 'jsx':
    case 'javascript':
      return 'js';
    case 'ts':
    case 'tsx':
    case 'typescript':
      return 'ts';
    default:
      return language;
  }
}

function getLang(child) {
  return getUnifiedLang(child.props['data-language']);
}

export function MultiCodeBlock(props) {
  const {codeBlocks, titles} = useMemo(() => {
    const defaultState = {
      codeBlocks: {},
      titles: {}
    };

    if (!Array.isArray(props.children)) {
      return defaultState;
    }

    return props.children.reduce((acc, child, index, array) => {
      const lang = getLang(child);
      if (lang) {
        return {
          ...acc,
          codeBlocks: {
            ...acc.codeBlocks,
            [lang]: child
          }
        };
      }

      if (child.props.className === 'gatsby-code-title') {
        const nextNode = array[index + 1];
        const title = child.props.children;
        const lang = getLang(nextNode);
        if (nextNode && title && lang) {
          return {
            ...acc,
            titles: {
              ...acc.titles,
              [lang]: title
            }
          };
        }
      }

      return acc;
    }, defaultState);
  }, [props.children]);

  const languages = useMemo(() => Object.keys(codeBlocks), [codeBlocks]);
  const [selectedLanguage, setSelectedLanguage] = useContext(
    SelectedLanguageContext
  );

  if (!languages.length) {
    return props.children;
  }

  function handleLanguageChange(language) {
    setSelectedLanguage(language);
    trackCustomEvent({
      category: GA_EVENT_CATEGORY_CODE_BLOCK,
      action: 'Change language',
      label: language
    });
  }

  const defaultLanguage = languages[0];
  const renderedLanguage =
    selectedLanguage in codeBlocks ? selectedLanguage : defaultLanguage;

  return (
    <Container>
      <MultiCodeBlockContext.Provider
        value={{
          selectedLanguage: renderedLanguage,
          languages: languages.map(lang => ({
            lang,
            label:
              // try to find a label or capitalize the provided lang
              langLabels[lang] || lang.charAt(0).toUpperCase() + lang.slice(1)
          })),
          onLanguageChange: handleLanguageChange
        }}
      >
        <div className="gatsby-code-title">{titles[renderedLanguage]}</div>
        {codeBlocks[renderedLanguage]}
      </MultiCodeBlockContext.Provider>
    </Container>
  );
}

MultiCodeBlock.propTypes = {
  children: PropTypes.node.isRequired
};
