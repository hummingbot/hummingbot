const algoliasearch = require('algoliasearch');
const chunk = require('lodash.chunk');
const report = require('gatsby-cli/lib/reporter');

/**
 * give back the same thing as this was called with.
 *
 * @param {any} obj what to keep the same
 */
const identity = obj => obj;

/**
 * Fetches all records for the current index from Algolia
 *
 * @param {AlgoliaIndex} index eg. client.initIndex('your_index_name');
 * @param {Array<String>} attributesToRetrieve eg. ['modified', 'slug']
 */
function fetchAlgoliaObjects(index, attributesToRetrieve = ['modified']) {
  return new Promise((resolve, reject) => {
    const browser = index.browseAll('', { attributesToRetrieve });
    const hits = {};

    browser.on('result', content => {
      if (Array.isArray(content.hits)) {
        content.hits.forEach(hit => {
          hits[hit.objectID] = hit;
        });
      }
    });
    browser.on('end', () => resolve(hits));
    browser.on('error', err => reject(err));
  });
}

exports.onPostBuild = async function ({ graphql }, options) {
  const {
    appId,
    apiKey,
    queries,
    enablePartialUpdates = false,
    concurrentQueries = true,
  } = options;

  const activity = report.activityTimer(`index to Algolia`);
  activity.start();

  const client = algoliasearch(appId, apiKey);

  setStatus(activity, `${queries.length} queries to index`);

  try {
    const jobs = [];
    for (const [queryIndex, queryOptions] of queries.entries()) {
      const queryPromise = doQuery({
        client,
        activity,
        queryOptions,
        queryIndex,
        graphql,
        options,
      });

      if (concurrentQueries) {
        jobs.push(queryPromise);
      } else {
        // await each individual query rather than batching them
        const res = await queryPromise;
        jobs.push(res);
      }
    }

    const jobResults = await Promise.all(jobs);

    if (enablePartialUpdates) {
      // Combine queries with the same index
      const cleanupJobs = jobResults.reduce((acc, { index, toRemove = {} }) => {
        const indexName = index.indexName;
        if (acc.hasOwnProperty(indexName)) {
          // If index already exists, combine fields to remove
          return {
            ...acc,
            [indexName]: {
              ...acc[indexName],
              toRemove: {
                ...acc[indexName].toRemove,
                ...toRemove,
              },
            },
          };
        } else {
          return {
            ...acc,
            [indexName]: {
              index,
              toRemove,
            },
          };
        }
      }, {});

      const cleanup = Object.keys(cleanupJobs).map(async function (indexName) {
        const { index, toRemove } = cleanupJobs[indexName];
        const isRemoved = Object.keys(toRemove);

        if (isRemoved.length) {
          setStatus(
            activity,
            `deleting ${isRemoved.length} objects from ${indexName} index`
          );
          const { taskID } = await index.deleteObjects(isRemoved);
          return index.waitTask(taskID);
        }
      });

      await Promise.all(cleanup);
    }
  } catch (err) {
    report.panic('failed to index to Algolia', err);
  }
  activity.end();
};

/**
 * Runs as individual query and updates the corresponding index on Algolia
 */
async function doQuery({
  client,
  activity,
  queryOptions,
  queryIndex,
  options,
  graphql,
}) {
  const {
    settings: mainSettings,
    indexName: mainIndexName,
    chunkSize = 1000,
    enablePartialUpdates = false,
    matchFields: mainMatchFields = ['modified'],
  } = options;

  const {
    indexName = mainIndexName,
    query,
    transformer = identity,
    settings = mainSettings,
    forwardToReplicas,
    matchFields = mainMatchFields,
  } = queryOptions;

  const setQueryStatus = status => {
    setStatus(activity, `Query #${queryIndex + 1} (${indexName}): ${status}`);
  };

  if (!query) {
    report.panic(
      `failed to index to Algolia. You did not give "query" to this query`
    );
  }
  if (!Array.isArray(matchFields) || !matchFields.length) {
    return report.panic(
      `failed to index to Algolia. Argument matchFields has to be an array of strings`
    );
  }

  const index = client.initIndex(indexName);
  const tempIndex = client.initIndex(`${indexName}_tmp`);
  const indexToUse = await getIndexToUse({
    index,
    tempIndex,
    enablePartialUpdates,
  });

  /* Use to keep track of what to remove afterwards */
  const toRemove = {};

  setQueryStatus('Executing query...');
  const result = await graphql(query);
  if (result.errors) {
    report.panic(
      `failed to index to Algolia, errors:\n ${JSON.stringify(result.errors)}`,
      result.errors
    );
  }

  const objects = (await transformer(result)).map(object => ({
    objectID: object.objectID || object.id,
    ...object,
  }));

  if (objects.length > 0 && !objects[0].objectID) {
    report.panic(
      `failed to index to Algolia. Query results do not have 'objectID' or 'id' key`
    );
  }

  setQueryStatus(`graphql resulted in ${objects.length} records`);

  let hasChanged = objects;
  if (enablePartialUpdates) {
    setQueryStatus(`Starting Partial updates...`);

    const algoliaObjects = await fetchAlgoliaObjects(indexToUse, matchFields);

    const nbMatchedRecords = Object.keys(algoliaObjects).length;
    setQueryStatus(`Found ${nbMatchedRecords} existing records`);

    if (nbMatchedRecords) {
      hasChanged = objects.filter(curObj => {
        if (matchFields.every(field => Boolean(curObj[field]) === false)) {
          report.panic(
            'when enablePartialUpdates is true, the objects must have at least one of the match fields. Current object:\n' +
              JSON.stringify(curObj, null, 2) +
              '\n' +
              'expected one of these fields:\n' +
              matchFields.join('\n')
          );
        }

        const ID = curObj.objectID;
        let extObj = algoliaObjects[ID];

        /* The object exists so we don't need to remove it from Algolia */
        delete algoliaObjects[ID];
        delete toRemove[ID];

        if (!extObj) return true;

        return matchFields.some(field => extObj[field] !== curObj[field]);
      });

      Object.keys(algoliaObjects).forEach(objectID => {
        // if the object has one of the matchFields, it should be removed,
        // but objects without matchFields are considered "not controlled"
        // and stay in the index
        if (matchFields.some(field => algoliaObjects[objectID][field])) {
          toRemove[objectID] = true;
        }
      });
    }

    setQueryStatus(
      `Partial updates – [insert/update: ${hasChanged.length}, total: ${objects.length}]`
    );
  }

  if (hasChanged.length) {
    const chunks = chunk(hasChanged, chunkSize);

    setQueryStatus(`Splitting in ${chunks.length} jobs`);

    /* Add changed / new objects */
    const chunkJobs = chunks.map(async function (chunked) {
      const { taskID } = await indexToUse.addObjects(chunked);
      return indexToUse.waitTask(taskID);
    });

    await Promise.all(chunkJobs);
  } else {
    setQueryStatus('No changes; skipping');
  }

  const settingsToApply = await getSettingsToApply({
    settings,
    index,
    tempIndex,
    indexToUse,
  });

  const { taskID } = await indexToUse.setSettings(settingsToApply, {
    forwardToReplicas,
  });

  await indexToUse.waitTask(taskID);

  if (indexToUse === tempIndex) {
    setQueryStatus('Moving copied index to main index...');
    await moveIndex(client, indexToUse, index);
  }

  setQueryStatus('Done!');

  return {
    index,
    toRemove,
  };
}

/**
 * moves the source index to the target index
 * @param client
 * @param sourceIndex
 * @param targetIndex
 * @return {Promise}
 */
async function moveIndex(client, sourceIndex, targetIndex) {
  const { taskID } = await client.moveIndex(
    sourceIndex.indexName,
    targetIndex.indexName
  );
  return targetIndex.waitTask(taskID);
}

/**
 * Does an Algolia index exist already
 *
 * @param index
 */
function indexExists(index) {
  return index
    .getSettings()
    .then(() => true)
    .catch(error => {
      if (error.statusCode !== 404) {
        throw error;
      }

      return false;
    });
}

/**
 * Hotfix the Gatsby reporter to allow setting status (not supported everywhere)
 *
 * @param {Object} activity reporter
 * @param {String} status status to report
 */
function setStatus(activity, status) {
  if (activity && activity.setStatus) {
    activity.setStatus(status);
  } else {
    console.log('[Algolia]', status);
  }
}

async function getIndexToUse({ index, tempIndex, enablePartialUpdates }) {
  const mainIndexExists = await indexExists(index);

  if (enablePartialUpdates && !mainIndexExists) {
    return createIndex(index);
  }

  if (!enablePartialUpdates && mainIndexExists) {
    return tempIndex;
  }

  return index;
}

async function getSettingsToApply({
  settings: givenSettings,
  index,
  tempIndex,
  indexToUse,
}) {
  const { replicaUpdateMode, ...settings } = givenSettings;
  const existingSettings = await index.getSettings().catch(e => {
    report.panic(`${e.toString()} ${index.indexName}`);
  });

  const replicasToSet = getReplicasToSet(
    settings.replicas,
    existingSettings.replicas,
    replicaUpdateMode
  );

  const requestedSettings = {
    ...(settings ? settings : existingSettings),
    replicas: replicasToSet,
  };

  // If we're building replicas, we don't want to add them to temporary indices
  if (indexToUse === tempIndex) {
    const { replicas, ...adjustedSettings } = requestedSettings;
    return adjustedSettings;
  }

  return requestedSettings;
}

function getReplicasToSet(
  givenReplicas = [],
  existingReplicas = [],
  replicaUpdateMode = 'merge'
) {
  if (replicaUpdateMode == 'replace') {
    return givenReplicas;
  }

  if (replicaUpdateMode === 'merge') {
    const replicas = new Set();
    existingReplicas.forEach(replica => replicas.add(replica));
    givenReplicas.forEach(replica => replicas.add(replica));

    return [...replicas];
  }
}

async function createIndex(index) {
  const { taskID } = await index.setSettings({});
  await index.waitTask(taskID);
  return index;
}
