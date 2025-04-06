# Copyright (c) 2015-2024 by Ron Frederick <ronf@timeheart.net> and others.
#
# This program and the accompanying materials are made available under
# the terms of the Eclipse Public License v2.0 which accompanies this
# distribution and is available at:
#
#     http://www.eclipse.org/legal/epl-2.0/
#
# This program may also be made available under the following secondary
# licenses when the conditions for such availability set forth in the
# Eclipse Public License v2.0 are satisfied:
#
#    GNU General Public License, Version 2.0, or any later versions of
#    that license
#
# SPDX-License-Identifier: EPL-2.0 OR GPL-2.0-or-later
#
# Contributors:
#     Ron Frederick - initial implementation, API, and documentation

"""Parser for SSH authorized_keys files"""

from typing import Dict, List, Mapping, Optional, Sequence
from typing import Set, Tuple, Union, cast

try:
    # pylint: disable=unused-import
    from .crypto import X509Name, X509NamePattern
    _x509_available = True
except ImportError: # pragma: no cover
    _x509_available = False

from .misc import ip_address, read_file
from .pattern import HostPatternList, WildcardPatternList
from .public_key import KeyImportError, SSHKey
from .public_key import SSHX509Certificate, SSHX509CertificateChain
from .public_key import import_public_key, import_certificate
from .public_key import import_certificate_subject


_EntryOptions = Mapping[str, object]

class _SSHAuthorizedKeyEntry:
    """An entry in an SSH authorized_keys list"""

    def __init__(self, line: str):
        self.key: Optional[SSHKey] = None
        self.cert: Optional[SSHX509Certificate] = None
        self.options: Dict[str, object] = {}

        try:
            self._import_key_or_cert(line)
            return
        except KeyImportError:
            pass

        line = self._parse_options(line)
        self._import_key_or_cert(line)

    def _import_key_or_cert(self, line: str) -> None:
        """Import key or certificate in this entry"""

        try:
            self.key = import_public_key(line)
            return
        except KeyImportError:
            pass

        try:
            self.cert = cast(SSHX509Certificate, import_certificate(line))

            if ('cert-authority' in self.options and
                    self.cert.subject != self.cert.issuer):
                raise ValueError('X.509 cert-authority entries must '
                                 'contain a root CA certificate')

            return
        except KeyImportError:
            pass

        if 'cert-authority' not in self.options:
            try:
                self.key = None
                self.cert = None
                self._add_subject('subject', import_certificate_subject(line))
                return
            except KeyImportError:
                pass

        raise KeyImportError('Unrecognized key, certificate, or subject')

    def _set_string(self, option: str, value: str) -> None:
        """Set an option with a string value"""

        self.options[option] = value

    def _add_environment(self, option: str, value: str) -> None:
        """Add an environment key/value pair"""

        if value.startswith('=') or '=' not in value:
            raise ValueError('Invalid environment entry in authorized_keys')

        name, value = value.split('=', 1)
        cast(Dict[str, str], self.options.setdefault(option, {}))[name] = value

    def _add_from(self, option: str, value: str) -> None:
        """Add a from host pattern"""

        from_patterns = cast(List[HostPatternList],
                             self.options.setdefault(option, []))
        from_patterns.append(HostPatternList(value))

    def _add_permitopen(self, option: str, value: str) -> None:
        """Add a permitopen host/port pair"""

        try:
            host, port_str = value.rsplit(':', 1)

            if host.startswith('[') and host.endswith(']'):
                host = host[1:-1]

            port = None if port_str == '*' else int(port_str)
        except ValueError:
            raise ValueError(f'Illegal permitopen value: {value}') from None

        permitted_opens = cast(Set[Tuple[str, Optional[int]]],
                               self.options.setdefault(option, set()))
        permitted_opens.add((host, port))

    def _add_principals(self, option: str, value: str) -> None:
        """Add a principals wildcard pattern list"""

        principal_patterns = cast(List[WildcardPatternList],
                                  self.options.setdefault(option, []))
        principal_patterns.append(WildcardPatternList(value))

    def _add_subject(self, option: str, value: str) -> None:
        """Add an X.509 subject pattern"""

        if _x509_available: # pragma: no branch
            subject_patterns = cast(List[X509NamePattern],
                                    self.options.setdefault(option, []))
            subject_patterns.append(X509NamePattern(value))

    _handlers = {
        'command':     _set_string,
        'environment': _add_environment,
        'from':        _add_from,
        'permitopen':  _add_permitopen,
        'principals':  _add_principals,
        'subject':     _add_subject
    }

    def _add_option(self) -> None:
        """Add an option value"""

        if self._option.startswith('='):
            raise ValueError('Missing option name in authorized_keys')

        if '=' in self._option:
            option, value = self._option.split('=', 1)

            handler = self._handlers.get(option)
            if handler:
                handler(self, option, value)
            else:
                values = cast(List[str], self.options.setdefault(option, []))
                values.append(value)
        else:
            self.options[self._option] = True

    def _parse_options(self, line: str) -> str:
        """Parse options in this entry"""

        self._option = ''

        idx = 0
        quoted = False
        escaped = False

        for idx, ch in enumerate(line):
            if escaped:
                self._option += ch
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == '"':
                quoted = not quoted
            elif quoted:
                self._option += ch
            elif ch in ' \t':
                break
            elif ch == ',':
                self._add_option()
                self._option = ''
            else:
                self._option += ch

        self._add_option()

        if quoted:
            raise ValueError('Unbalanced quote in authorized_keys')
        elif escaped:
            raise ValueError('Unbalanced backslash in authorized_keys')

        return line[idx:].strip()

    def match_options(self, client_host: str, client_addr: str,
                      cert_principals: Optional[Sequence[str]],
                      cert_subject: Optional['X509Name'] = None) -> bool:
        """Match "from", "principals" and "subject" options in entry"""

        from_patterns = cast(List[HostPatternList], self.options.get('from'))

        if from_patterns:
            client_ip = ip_address(client_addr)

            if not all(pattern.matches(client_host, client_addr, client_ip)
                       for pattern in from_patterns):
                return False

        principal_patterns = cast(List[WildcardPatternList],
                                  self.options.get('principals'))

        if cert_principals is not None and principal_patterns is not None:
            if not all(any(pattern.matches(principal)
                           for principal in cert_principals)
                       for pattern in principal_patterns):
                return False

        subject_patterns = cast(List['X509NamePattern'],
                                self.options.get('subject'))

        if cert_subject is not None and subject_patterns is not None:
            if not all(pattern.matches(cert_subject)
                       for pattern in subject_patterns):
                return False

        return True


class SSHAuthorizedKeys:
    """An SSH authorized keys list"""

    def __init__(self, authorized_keys: Optional[str] = None):
        self._user_entries: List[_SSHAuthorizedKeyEntry] = []
        self._ca_entries: List[_SSHAuthorizedKeyEntry] = []
        self._x509_entries: List[_SSHAuthorizedKeyEntry] = []

        if authorized_keys:
            self.load(authorized_keys)

    def load(self, authorized_keys: str) -> None:
        """Load authorized keys data into this object"""

        for line in authorized_keys.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            try:
                entry = _SSHAuthorizedKeyEntry(line)
            except KeyImportError:
                continue

            if entry.key:
                if 'cert-authority' in entry.options:
                    self._ca_entries.append(entry)
                else:
                    self._user_entries.append(entry)
            else:
                self._x509_entries.append(entry)

        if (not self._user_entries and not self._ca_entries and
                not self._x509_entries):
            raise ValueError('No valid entries found')

    def validate(self, key: SSHKey, client_host: str, client_addr: str,
                 cert_principals: Optional[Sequence[str]] = None,
                 ca: bool = False) -> Optional[Mapping[str, object]]:
        """Return whether a public key or CA is valid for authentication"""

        for entry in self._ca_entries if ca else self._user_entries:
            if (entry.key == key and
                    entry.match_options(client_host, client_addr,
                                        cert_principals)):
                return entry.options

        return None

    def validate_x509(self, cert: SSHX509CertificateChain, client_host: str,
                      client_addr: str) -> Tuple[Optional[_EntryOptions],
                                                 Optional[SSHX509Certificate]]:
        """Return whether an X.509 certificate is valid for authentication"""

        for entry in self._x509_entries:
            if (entry.cert and 'cert-authority' not in entry.options and
                    (cert.key != entry.cert.key or
                     cert.subject != entry.cert.subject)):
                continue # pragma: no cover (work around bug in coverage tool)

            if entry.match_options(client_host, client_addr,
                                   cert.user_principals, cert.subject):
                return entry.options, entry.cert

        return None, None

def import_authorized_keys(data: str) -> SSHAuthorizedKeys:
    """Import SSH authorized keys

       This function imports public keys and associated options in
       OpenSSH authorized keys format.

       :param data:
           The key data to import.
       :type data: `str`

       :returns: An :class:`SSHAuthorizedKeys` object

    """

    return SSHAuthorizedKeys(data)


def read_authorized_keys(filelist: Union[str, Sequence[str]]) -> \
        SSHAuthorizedKeys:
    """Read SSH authorized keys from a file or list of files

       This function reads public keys and associated options in
       OpenSSH authorized_keys format from a file or list of files.

       :param filelist:
           The file or list of files to read the keys from.
       :type filenlist: `str` or `list` of `str`

       :returns: An :class:`SSHAuthorizedKeys` object

    """

    authorized_keys = SSHAuthorizedKeys()

    if isinstance(filelist, str):
        files: Sequence[str] = [filelist]
    else:
        files = filelist

    for filename in files:
        authorized_keys.load(read_file(filename, 'r'))

    return authorized_keys
