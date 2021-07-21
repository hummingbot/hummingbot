const got = require('got')
const path = require('path')
const semver = require('semver')
const { writeFile } = require('fs').promises

async function getJSONFromCDN (urlPath) {
  const response = await got(`https://cdn.jsdelivr.net/gh/${urlPath}`)
  return JSON.parse(response.body)
}

async function fetchElectronVersions () {
  return (await getJSONFromCDN('electron/releases/lite.json')).map(metadata => metadata.version)
}

async function fetchNodeVersions () {
  const schedule = await getJSONFromCDN('nodejs/Release/schedule.json')
  const versions = {}

  for (const [majorVersion, metadata] of Object.entries(schedule)) {
    if (majorVersion.startsWith('v0')) {
      continue
    }
    const version = `${majorVersion.slice(1)}.0.0`
    const lts = metadata.hasOwnProperty('lts') ? [metadata.lts, metadata.maintenance] : false
    versions[version] = {
      runtime: 'node',
      target: version,
      lts: lts,
      future: new Date(Date.parse(metadata.start)) > new Date()
    }
  }

  return versions
}

async function fetchAbiVersions () {
  return (await getJSONFromCDN('nodejs/node/doc/abi_version_registry.json')).NODE_MODULE_VERSION
}

async function main () {
  const nodeVersions = await fetchNodeVersions()
  const abiVersions = await fetchAbiVersions()
  const electronVersions = await fetchElectronVersions()

  const abiVersionSet = new Set()
  const supportedTargets = []
  for (const abiVersion of abiVersions) {
    if (abiVersion.modules <= 66) {
      // Don't try to parse any ABI versions older than 60
      break
    } else if (abiVersion.runtime === 'electron' && abiVersion.modules < 70) {
      // Don't try to parse Electron ABI versions below Electron 5
      continue
    }

    let target
    if (abiVersion.runtime === 'node') {
      const nodeVersion = `${abiVersion.versions.replace('.0.0-pre', '')}.0.0`
      target = nodeVersions[nodeVersion]
      if (!target) {
        continue
      }
    } else {
      target = {
        runtime: abiVersion.runtime === 'nw.js' ? 'node-webkit' : abiVersion.runtime,
        target: abiVersion.versions,
        lts: false,
        future: false
      }
      if (target.runtime === 'electron') {
        target.target = `${target.target}.0.0`
        const constraint = /^[0-9]/.test(abiVersion.versions) ? `>= ${abiVersion.versions}` : abiVersion.versions
        if (!electronVersions.find(electronVersion => semver.satisfies(electronVersion, constraint))) {
          target.target = `${target.target}-beta.1`
          target.future = true
        }
      }
    }
    target.abi = abiVersion.modules.toString()

    const key = [target.runtime, target.target].join('-')
    if (abiVersionSet.has(key)) {
      continue
    }

    abiVersionSet.add(key)
    supportedTargets.unshift(target)
  }

  await writeFile(path.resolve(__dirname, '..', 'abi_registry.json'), JSON.stringify(supportedTargets, null, 2))
}

main()
