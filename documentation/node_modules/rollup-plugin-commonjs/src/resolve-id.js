import { statSync } from 'fs';
import { dirname, resolve, sep } from 'path';
import {
	getExternalProxyId,
	getIdFromProxyId,
	getProxyId,
	HELPERS_ID,
	PROXY_SUFFIX
} from './helpers';

function getCandidatesForExtension(resolved, extension) {
	return [resolved + extension, resolved + `${sep}index${extension}`];
}

function getCandidates(resolved, extensions) {
	return extensions.reduce(
		(paths, extension) => paths.concat(getCandidatesForExtension(resolved, extension)),
		[resolved]
	);
}

export function getResolveId(extensions) {
	function resolveExtensions(importee, importer) {
		if (importee[0] !== '.' || !importer) return; // not our problem

		const resolved = resolve(dirname(importer), importee);
		const candidates = getCandidates(resolved, extensions);

		for (let i = 0; i < candidates.length; i += 1) {
			try {
				const stats = statSync(candidates[i]);
				if (stats.isFile()) return { id: candidates[i] };
			} catch (err) {
				/* noop */
			}
		}
	}

	function resolveId(importee, importer) {
		const isProxyModule = importee.endsWith(PROXY_SUFFIX);
		if (isProxyModule) {
			importee = getIdFromProxyId(importee);
		} else if (importee.startsWith('\0')) {
			if (importee === HELPERS_ID) {
				return importee;
			}
			return null;
		}

		if (importer && importer.endsWith(PROXY_SUFFIX)) {
			importer = getIdFromProxyId(importer);
		}

		return this.resolve(importee, importer, { skipSelf: true }).then(resolved => {
			if (!resolved) {
				resolved = resolveExtensions(importee, importer);
			}
			if (isProxyModule) {
				if (!resolved) {
					return { id: getExternalProxyId(importee), external: false };
				}
				resolved.id = (resolved.external ? getExternalProxyId : getProxyId)(resolved.id);
				resolved.external = false;
				return resolved;
			}
			return resolved;
		});
	}

	return resolveId;
}
