import PageLayout from './src/components/page-layout';
import React from 'react';

export const onRenderBody = ({setPostBodyComponents, setHeadComponents}, {ffWidgetId}) => {
  if (ffWidgetId) {
    setHeadComponents([
      <script
        key="feedback"
        dangerouslySetInnerHTML={{
          __html: `
          var ffWidgetId = '${ffWidgetId}';
          var ffWidgetScript = document.createElement("script");
          ffWidgetScript.type = "text/javascript";
          ffWidgetScript.src = 'https://freddyfeedback.com/widget/freddyfeedback.js';
          document.head.appendChild(ffWidgetScript);
        `,
        }}
      />
    ]);
  }

  setPostBodyComponents([
    React.createElement('script', {
      key: 'docsearch',
      src:
        'https://cdn.jsdelivr.net/npm/docsearch.js@2/dist/cdn/docsearch.min.js'
    })
  ]);
};

export const wrapPageElement = (
  {element, props}, // eslint-disable-line react/prop-types
  pluginOptions
) => (
  <PageLayout {...props} pluginOptions={pluginOptions}>
    {element}
  </PageLayout>
);
