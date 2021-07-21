# Gatsby plugin Algolia

> This plugin is in _beta_ and not officially supported yet
>
> Feel free to open issues for any questions or ideas

You can specify a list of queries to run and how to transform them into an array of objects to index. When you run `gatsby build`, it will publish those to Algolia.

Here we have an example with some data that might not be very relevant, but will work with the default configuration of `gatsby new`

```shell
$ yarn add gatsby-plugin-algolia
```

First add credentials to a .env file, which you won't commit. If you track this in your file, and especially if the site is open source, you will leak your admin API key. This would mean anyone is able to change anything on your Algolia index.

```
// .env.production
ALGOLIA_APP_ID=XXX
ALGOLIA_API_KEY=XXX
ALGOLIA_INDEX_NAME=XXX
```

```js
require('dotenv').config({
  path: `.env.${process.env.NODE_ENV}`,
});

// gatsby-config.js
const myQuery = `{
  allSitePage {
    edges {
      node {
        # try to find a unique id for each node
        # if this field is absent, it's going to
        # be inserted by Algolia automatically
        # and will be less simple to update etc.
        objectID: id
        component
        path
        componentChunkName
        jsonName
        internal {
          type
          contentDigest
          owner
        }
      }
    }
  }
}`;

const queries = [
  {
    query: myQuery,
    transformer: ({ data }) => data.allSitePage.edges.map(({ node }) => node), // optional
    indexName: 'index name to target', // overrides main index name, optional
    settings: {
      // optional, any index settings
    },
    matchFields: ['slug', 'modified'], // Array<String> overrides main match fields, optional
  },
];

module.exports = {
  plugins: [
    {
      // This plugin must be placed last in your list of plugins to ensure that it can query all the GraphQL data
      resolve: `gatsby-plugin-algolia`,
      options: {
        appId: process.env.ALGOLIA_APP_ID,
        // Use Admin API key without GATSBY_ prefix, so that the key isn't exposed in the application
        // Tip: use Search API key with GATSBY_ prefix to access the service from within components
        apiKey: process.env.ALGOLIA_API_KEY,
        indexName: process.env.ALGOLIA_INDEX_NAME, // for all queries
        queries,
        chunkSize: 10000, // default: 1000
        settings: {
          // optional, any index settings
        },
        enablePartialUpdates: true, // default: false
        matchFields: ['slug', 'modified'], // Array<String> default: ['modified']
        concurrentQueries: false, // default: true
      },
    },
  ],
};
```

The index will be synchronised with the provided index name on Algolia on the `build` step in Gatsby. This is not done earlier to prevent you going over quota while developing.

## Partial Updates

By default all records will be reindexed on every build. To enable only indexing the new, changed and deleted records include the following in the options of the plugin:

```js
  resolve: `gatsby-plugin-algolia`,
  options: {
    /* ... */
    enablePartialUpdates: true,
    /* (optional) Fields to use for comparing if the index object is different from the new one */
    /* By default it uses a field called "modified" which could be a boolean | datetime string */
    matchFields: ['slug', 'modified'], // Array<String> default: ['modified']
  }
```

This saves a lot of Algolia operations since you don't reindex everything on every build.

Adding `matchFields` is useful to decide whether an object has been changed since the last time it was indexed. If you save e.g. a timestamp of the record, you can avoid reindexing when it has not changed.

If you have objects which come from another indexing process (wordpress, magento, shopify, custom script...), make sure that they do not have any of the `matchFields`, so they stay in the index regardless of reindex.

### Advanced

You can also specify `matchFields` per query to check for different fields based on the type of objects you are indexing.

## Settings

You can set settings for each index individually (per query), or otherwise it will keep your existing settings.

### Replicas

For replica settings, extra care is taken to make sure only apply replicas to non-temporary indices.

If you pass `replicaUpdateMode: 'replace'` in the index settings, you can choose to update the replicas fully with those in the settings.

If you pass `replicaUpdateMode: 'merge'` in the index settings, the replica settings will combine the replicas set on your dashboard with the additional ones you set via index settings here.

## Concurrent Queries

Sometimes, on limited platforms like Netlify, concurrent queries to the same index can lead to unexpected results or hanging builds. Setting `concurrentQueries` to `false` makes it such that queries are run sequentially rather than concurrently, which may solve some concurrent access issues. Be aware that this option may make indexing take longer than it would otherwise.

## Transformer

The `transformer` field accepts a function and optionally you may provide an `async` function. This is useful when you want to change e.g. "edges.node" to simply an array.

# Feedback

This is the very first version of our plugin and isn't yet officially supported. Please leave all your feedback in GitHub issues 😊
