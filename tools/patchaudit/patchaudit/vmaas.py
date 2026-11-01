"""Latest source build in the public Red Hat VMaaS v3 catalogue.

The catalogue indexes repository membership on binary RPMs. SRPM names must
therefore be expanded before selecting a build; source-only tree rows do not
prove that a build was shipped in the requested RHEL repository.
"""
import hashlib
import json
import os
import re
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from functools import cmp_to_key
from itertools import islice
from typing import NamedTuple, Optional
from urllib.parse import quote

from . import __version__
from .httpclient import HttpClient, UrllibTransport
from .rpmvercmp import rpmvercmp
from .vex import parse_rhel, prepare_cache, read_cache, write_cache

BASE_URL = 'https://console.redhat.com/api/vmaas/v3'
_CACHE_SCHEMA = 1
_NAME = re.compile(r'^[A-Za-z0-9_+.-]+$')
_PART = re.compile(r'^[A-Za-z0-9_+.~^:]+$')


class VmaasError(Exception):
    """The catalogue could not establish a complete, trustworthy answer."""


class VmaasSettings(NamedTuple):
    cache_dir: Optional[str] = None
    cache_ttl: int = 3600
    arch: str = 'x86_64'
    retries: int = 3
    timeout: float = 30


def _rpm(value):
    """Parse NEVRA, keeping epoch until the final public NVR is rendered."""
    try:
        if not isinstance(value, str):
            raise ValueError()
        nvr, arch = value.rsplit('.', 1)
        name, version, release = nvr.rsplit('-', 2)
        if (not _NAME.fullmatch(name) or not _PART.fullmatch(version) or
                not _PART.fullmatch(release) or ':' in release or not _NAME.fullmatch(arch)):
            raise ValueError()
        epoch = 0
        if ':' in version:
            epoch_text, version = version.split(':', 1)
            if not epoch_text.isdigit() or not version or ':' in version:
                raise ValueError()
            epoch = int(epoch_text)
        return name, epoch, version, release, arch
    except (ValueError, AttributeError):
        raise VmaasError('VMaaS: invalid package NEVRA %r' % value) from None


def _evr_compare(one, two):
    return ((one[1] > two[1]) - (one[1] < two[1]) or
            rpmvercmp(one[2], two[2]) or rpmvercmp(one[3], two[3]))


def _mapping(doc, field):
    if not isinstance(doc, dict) or not isinstance(doc.get(field), dict):
        raise VmaasError('VMaaS: invalid %s response' % field)
    return doc[field]


def _complete(doc):
    # The GET API does not document pagination arguments. Refuse truncated
    # trees instead of assuming a query parameter was honoured by the server.
    if (type(doc.get('page')) is not int or type(doc.get('pages')) is not int or
            doc['page'] != 1 or doc['pages'] != 1 or
            type(doc.get('page_size')) is not int or doc['page_size'] < 1):
        raise VmaasError('VMaaS: incomplete or invalid pagination')


class VmaasClient:
    def __init__(self, settings=VmaasSettings(), transport=None, sleeper=None):
        self.settings = settings
        self._http = HttpClient(transport=transport or UrllibTransport(settings.timeout),
                                token=None, retries=settings.retries,
                                sleeper=sleeper or time.sleep)
        self._cache_dir = (prepare_cache(settings.cache_dir)
                           if settings.cache_dir else None)
        self._sources = {}

    def _get(self, path, value):
        url = BASE_URL + path + quote(value, safe='')
        response = self._http.get(url, headers={
            'Accept': 'application/json', 'User-Agent': 'patchaudit/%s (+VMaaS client)' % __version__}, params={})
        if isinstance(response, str):
            raise VmaasError('VMaaS: ' + response.removeprefix('gitlab: '))
        if response.status != 200:
            raise VmaasError('VMaaS: HTTP %s for %s' % (response.status, url))
        if not isinstance(response.body, dict):
            raise VmaasError('VMaaS: invalid JSON object for %s' % url)
        return response.body

    def _repo_matches(self, repository, rhel):
        if not isinstance(repository, dict) or any(not isinstance(repository.get(key), str)
                                                  for key in ('label', 'basearch', 'releasever')):
            raise VmaasError('VMaaS: invalid repository metadata')
        major = rhel.split('.')[0]
        arch = self.settings.arch
        if repository['basearch'] != arch or repository['releasever'] != rhel:
            return False
        support = r'(?:-(?:eus|e4s|e6s|aus|tus))?' if '.' in rhel else ''
        # Only the ordinary OS content sets. Layered, RHUI, beta and debug
        # repositories cannot establish the latest ordinary RHEL build.
        families = [r'rhel-%s-for-%s-(?:baseos|appstream)%s-rpms' % (major, re.escape(arch), support),
                    r'codeready-builder-for-rhel-%s-%s%s-rpms' % (major, re.escape(arch), support)]
        return any(re.fullmatch(pattern, repository['label']) for pattern in families)

    def _tree(self, name):
        # This endpoint interprets the path as a POSIX regexp, even for
        # literal package names. A hyphen is already literal outside [].
        pattern = re.escape(name).replace(r'\-', '-')
        doc = self._get('/pkgtree/', pattern)
        packages = _mapping(doc, 'package_name_list')
        _complete(doc)
        if name not in packages or not isinstance(packages[name], list):
            raise VmaasError('VMaaS: missing or invalid package tree for %s' % name)
        for entry in packages[name]:
            if not isinstance(entry, dict):
                raise VmaasError('VMaaS: invalid package tree entry')
            parsed = _rpm(entry.get('nevra'))
            if parsed[0] != name:
                raise VmaasError('VMaaS: package tree name does not match request')
            if parsed[4] != 'src' and 'repositories' not in entry:
                raise VmaasError('VMaaS: missing binary repository metadata')
            repositories = entry.get('repositories', [])
            if not isinstance(repositories, list):
                raise VmaasError('VMaaS: invalid repositories list')
            yield entry, parsed, repositories

    def _stream_matches(self, entry, stream):
        nevra = entry['nevra']
        errata = entry.get('errata')
        if not isinstance(errata, list) or not errata:
            raise VmaasError('VMaaS: cannot verify module stream for %s' % nevra)
        found = set()
        for erratum in errata:
            if not isinstance(erratum, dict) or not isinstance(erratum.get('name'), str) or not erratum['name']:
                raise VmaasError('VMaaS: invalid erratum metadata')
            name = erratum['name']
            doc = self._get('/errata/', name)
            details = _mapping(doc, 'errata_list')
            _complete(doc)
            if not isinstance(details.get(name), dict) or not isinstance(details[name].get('modules_list'), list):
                raise VmaasError('VMaaS: invalid module metadata for %s' % name)
            for module in details[name]['modules_list']:
                if (not isinstance(module, dict) or
                        any(not isinstance(module.get(key), str) or not module[key]
                            for key in ('module_name', 'module_stream')) or
                        not isinstance(module.get('package_list'), list) or
                        any(not isinstance(package, str) for package in module['package_list'])):
                    raise VmaasError('VMaaS: invalid module package membership')
                if nevra in module['package_list']:
                    found.add(module['module_name'] + ':' + module['module_stream'])
        if not found:
            raise VmaasError('VMaaS: cannot verify module stream for %s' % nevra)
        return any(value == stream if ':' in stream else value.split(':', 1)[1] == stream
                   for value in found)

    def _source(self, entry):
        nevra = entry['nevra']
        if nevra in self._sources:
            return self._sources[nevra]
        packages = _mapping(self._get('/packages/', nevra), 'package_list')
        if not isinstance(packages.get(nevra), dict):
            raise VmaasError('VMaaS: missing package details for %s' % nevra)
        source = _rpm(packages[nevra].get('source_package'))
        if source[4] != 'src':
            raise VmaasError('VMaaS: invalid source package architecture')
        self._sources[nevra] = source
        return source

    def _resolve_sources(self, candidates):
        """Bound both active and queued GETs; stop submitting on failure."""
        remaining = iter(candidates)
        sources = {}
        with ThreadPoolExecutor(max_workers=8, thread_name_prefix='vmaas') as pool:
            pending = {pool.submit(self._source, entry): entry['nevra']
                       for entry, _ in islice(remaining, 8)}
            try:
                while pending:
                    done, _ = wait(pending, return_when=FIRST_COMPLETED)
                    # Check the entire completed batch before scheduling more:
                    # an already failed neighbour must stop the next batch.
                    batch = [(pending[future], future.result()) for future in done]
                    sources.update(batch)
                    for future in done:
                        del pending[future]
                    for entry, _ in islice(remaining, len(done)):
                        pending[pool.submit(self._source, entry)] = entry['nevra']
            except BaseException:
                for future in pending:
                    future.cancel()
                raise
        return sources

    def latest(self, package, rhel, stream=None, aliases=()):
        try:
            rhel = parse_rhel(rhel)
        except ValueError as exc:
            raise VmaasError(str(exc)) from exc
        if int(rhel.split('.')[0]) < 8:
            raise VmaasError('VMaaS: latest build lookup supports RHEL 8 and newer')
        if (not isinstance(package, str) or not _NAME.fullmatch(package) or
                not isinstance(self.settings.arch, str) or not _NAME.fullmatch(self.settings.arch) or
                isinstance(aliases, str) or any(not isinstance(name, str) or not _NAME.fullmatch(name) for name in aliases) or
                (stream is not None and (not isinstance(stream, str) or not stream.strip()))):
            raise VmaasError('VMaaS: invalid package, architecture, alias or stream')
        aliases = tuple(sorted(set(aliases)))
        key = [package, rhel, stream, list(aliases), self.settings.arch]
        cache_path = (os.path.join(self._cache_dir, hashlib.sha256(json.dumps(key).encode()).hexdigest() + '.json')
                      if self._cache_dir else None)
        if cache_path and self.settings.cache_ttl > 0:
            cached = read_cache(cache_path, self.settings.cache_ttl)
            if self._valid_cache(cached, key):
                return cached['result']
            try:
                os.unlink(cache_path)
            except OSError:
                pass
        result = self._latest(package, rhel, stream, aliases)
        if cache_path:
            write_cache(cache_path, json.dumps({'schema': _CACHE_SCHEMA, 'key': key, 'result': result}).encode())
        return result

    @staticmethod
    def _valid_cache(cached, key):
        if not isinstance(cached, dict) or cached.get('schema') != _CACHE_SCHEMA or cached.get('key') != key or 'result' not in cached:
            return False
        result = cached['result']
        if result is None:
            return True
        if not isinstance(result, str):
            return False
        try:
            parsed = _rpm(result + '.src')
        except VmaasError:
            return False
        return ':' not in result and '%s-%s-%s' % (parsed[0], parsed[2], parsed[3]) == result

    def _latest(self, package, rhel, stream, aliases):
        source_map = _mapping(self._get('/package_names/srpms/', package), 'srpm_name_list')
        if any(not isinstance(name, str) or not isinstance(repositories, dict) for name, repositories in source_map.items()):
            raise VmaasError('VMaaS: invalid source package mapping')
        mapped = set()
        for repositories in source_map.values():
            for label, binaries in repositories.items():
                if (not isinstance(label, str) or not isinstance(binaries, list) or
                        any(not isinstance(name, str) or not _NAME.fullmatch(name) for name in binaries)):
                    raise VmaasError('VMaaS: invalid source package binary names')
        if package in source_map:
            mapped = {name for binaries in source_map[package].values() for name in binaries}
            names = mapped | set(aliases)
        else:
            names = {package, *aliases}
        candidates = []
        for name in sorted(names):
            for entry, parsed, repositories in self._tree(name):
                matches = [self._repo_matches(repository, rhel) for repository in repositories]
                if parsed[4] not in (self.settings.arch, 'noarch') or not any(matches):
                    continue
                modular = 'module' in parsed[3]
                if bool(stream) != modular:
                    continue
                candidates.append((entry, parsed))
        # RPM subpackages may override their source's version and epoch
        # (e.g. rubygem-rake from ruby). Only actual source EVRs establish
        # source ordering; every eligible binary must be resolved first.
        sources = self._resolve_sources(candidates)
        resolved = [(entry, parsed, sources[entry['nevra']]) for entry, parsed in candidates]
        resolved.sort(key=cmp_to_key(lambda one, two: _evr_compare(one[2], two[2])), reverse=True)
        streams = {}

        def stream_matches(entry):
            if not stream:
                return True
            if entry['nevra'] not in streams:
                streams[entry['nevra']] = self._stream_matches(entry, stream)
            return streams[entry['nevra']]

        expected_source = package if package in source_map else None
        if not expected_source and aliases:
            # A binary request defines its source cohort. An alias must not
            # replace it with a newer build of an unrelated source package.
            for entry, parsed, source in resolved:
                if parsed[0] == package and stream_matches(entry):
                    expected_source = source[0]
                    break
        for entry, parsed, source in resolved:
            if expected_source and source[0] != expected_source:
                # The SRPM mapping is a historical union of binary names.
                # A name may since have moved to a different source package.
                continue
            if expected_source is None and parsed[0] != package and source[0] != package:
                raise VmaasError('VMaaS: cannot verify alias source package identity')
            if not stream_matches(entry):
                continue
            return '%s-%s-%s' % (source[0], source[2], source[3])
        return None
