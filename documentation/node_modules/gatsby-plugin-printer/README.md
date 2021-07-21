# gatsby-plugin-printer

## Node API

This is a declarative API that lets the library control batching, caching, etc. Creating `Printer` nodes via this API doesn't give you a `fileName` back, so you would have to specify one.

```js
import { createPrinterNode } from "gatsby-plugin-printer";

exports.onCreateNode = ({ actions, node }) => {
  if (node.internal.type === "Mdx") {
    // createPrinterNode creates an object that can be passed in
    // to `createNode`
    const printerNode = createPrinterNode({
      id: node.id,
      // fileName is something you can use in opengraph images, etc
      fileName: slugify(node.title),
      // renderDir is relative to `public` by default
      outputDir: "blog-post-images",
      // data gets passed directly to your react component
      data: node,
      // the component to use for rendering. Will get batched with
      // other nodes that use the same component
      component: require.resolve("./src/printer-components/blog-post.js")
    });
  }
};
```

## Manual control

You can also import and use `runScreenshots` but note that you will have to control batching, etc yourself.

```js
exports.onPostBuild = ({graphql}) => {

  const data = await graphql(`
    {
      allBlogPost {
        nodes {
          title
        }
      }
    }
  `).then(r => {
    if (r.errors) {
      reporter.error(r.errors.join(`, `));
    }
    return r.data;
  });

const titles = data.allBlogPost.nodes.map(({ title }) => ({
	id: slugify(title),
  title,
  }));

  await runScreenshots({
  	data: titles,
  	component: require.resolve('./src/printer-components/blog-post'),
  	outputDir: 'rainbow-og-images'
  });
}
```
