# Copyright (c) 2020-2024 by Ron Frederick <ronf@timeheart.net> and others.
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

"""Parser for OpenSSH config files"""

import os
import re
import shlex
import socket
import subprocess

from hashlib import sha1
from pathlib import Path, PurePath
from subprocess import DEVNULL
from typing import Callable, Dict, List, NoReturn, Optional, Sequence
from typing import Set, Tuple, Union, cast

from .constants import DEFAULT_PORT
from .logging import logger
from .misc import DefTuple, FilePath, ip_address
from .pattern import HostPatternList, WildcardPatternList


ConfigPaths = Union[None, FilePath, Sequence[FilePath]]


_token_pattern = re.compile(r'%(.)')
_env_pattern = re.compile(r'\${(.*)}')


def _exec(cmd: str) -> bool:
    """Execute a command and return if exit status is 0"""

    return subprocess.run(cmd, check=False, shell=True, stdin=DEVNULL,
                          stdout=DEVNULL, stderr=DEVNULL).returncode == 0


class ConfigParseError(ValueError):
    """Configuration parsing exception"""


class SSHConfig:
    """Settings from an OpenSSH config file"""

    _conditionals = {'match'}
    _no_split: Set[str] = set()
    _percent_expand = {'AuthorizedKeysFile'}
    _handlers: Dict[str, Tuple[str, Callable]] = {}

    def __init__(self, last_config: Optional['SSHConfig'], reload: bool,
                 canonical: bool, final: bool):
        if last_config:
            self._last_options = last_config.get_options(reload)
        else:
            self._last_options = {}

        self._canonical = canonical
        self._final = True if final else None
        self._default_path = Path('~', '.ssh').expanduser()
        self._path = Path()
        self._line_no = 0
        self._matching = True
        self._options = self._last_options.copy()
        self._tokens: Dict[str, str] = {}

        self.loaded = False

    def _error(self, reason: str) -> NoReturn:
        """Raise a configuration parsing error"""

        raise ConfigParseError(f'{self._path} line {self._line_no}: {reason}')

    def _match_val(self, match: str) -> object:
        """Return the value to match against in a match condition"""

        raise NotImplementedError

    def _set_tokens(self) -> None:
        """Set the tokens available for percent expansion"""

        raise NotImplementedError

    def _expand_token(self, match):
        """Expand a percent token reference"""

        try:
            token = match.group(1)
            return self._tokens[token]
        except KeyError:
            if token == 'd':
                raise ConfigParseError('Home directory is '
                                       'not available') from None
            elif token == 'i':
                raise ConfigParseError('User id not available') from None
            else:
                raise ConfigParseError('Invalid token expansion: ' +
                                       token) from None

    @staticmethod
    def _expand_env(match):
        """Expand an environment variable reference"""

        try:
            var = match.group(1)
            return os.environ[var]
        except KeyError:
            raise ConfigParseError('Invalid environment expansion: ' +
                                   var) from None

    def _expand_val(self, value: str) -> str:
        """Perform percent token and environment expansion on a string"""

        return _env_pattern.sub(self._expand_env,
                                _token_pattern.sub(self._expand_token, value))

    def _include(self, option: str, args: List[str]) -> None:
        """Read config from a list of other config files"""

        # pylint: disable=unused-argument

        old_path = self._path

        for pattern in args:
            path = Path(pattern).expanduser()

            if path.anchor:
                pattern = str(Path(*path.parts[1:]))
                path = Path(path.anchor)
            else:
                path = self._default_path

            paths = list(path.glob(pattern))

            if not paths:
                logger.debug1(f'Config pattern "{pattern}" matched no files')

            for path in paths:
                self.parse(path)

        self._path = old_path
        args.clear()

    def _match(self, option: str, args: List[str]) -> None:
        """Begin a conditional block"""

        # pylint: disable=unused-argument

        matching = True

        while args:
            match = args.pop(0).lower()

            if match[0] == '!':
                match = match[1:]
                negated = True
            else:
                negated = False

            if match == 'final' and self._final is None:
                self._final = False

            if match == 'all':
                result = True
            elif match == 'canonical':
                result = self._canonical
            elif match == 'final':
                result = cast(bool, self._final)
            else:
                match_val = self._match_val(match)

                if match != 'exec' and match_val is None:
                    self._error(f'Invalid match condition {match}')

                try:
                    arg = args.pop(0)
                except IndexError:
                    self._error(f'Missing {match} match pattern')

                if matching:
                    if match == 'exec':
                        result = _exec(arg)
                    elif match in ('address', 'localaddress'):
                        host_pat = HostPatternList(arg)
                        ip = ip_address(cast(str, match_val)) \
                            if match_val else None
                        result = host_pat.matches(None, match_val, ip)
                    else:
                        wild_pat = WildcardPatternList(arg)
                        result = wild_pat.matches(match_val)

            if matching and result == negated:
                matching = False

        self._matching = matching

    def _set_bool(self, option: str, args: List[str]) -> None:
        """Set a boolean config option"""

        value_str = args.pop(0).lower()

        if value_str in ('yes', 'true'):
            value = True
        elif value_str in ('no', 'false'):
            value = False
        else:
            self._error(f'Invalid {option} boolean value: {value_str}')

        if option not in self._options:
            self._options[option] = value

    def _set_bool_or_str(self, option: str, args: List[str]) -> None:
        """Set a boolean or string config option"""

        value_str = args.pop(0)
        value_lower = value_str.lower()

        if value_lower in ('yes', 'true'):
            value: Union[bool, str] = True
        elif value_lower in ('no', 'false'):
            value = False
        else:
            value = value_str

        if option not in self._options:
            self._options[option] = value

    def _set_int(self, option: str, args: List[str]) -> None:
        """Set an integer config option"""

        value_str = args.pop(0)

        try:
            value = int(value_str)
        except ValueError:
            self._error(f'Invalid {option} integer value: {value_str}')

        if option not in self._options:
            self._options[option] = value

    def _set_string(self, option: str, args: List[str]) -> None:
        """Set a string config option"""

        value_str = args.pop(0)

        if value_str.lower() == 'none':
            value = None
        else:
            value = value_str

        if option not in self._options:
            self._options[option] = value

    def _append_string(self, option: str, args: List[str]) -> None:
        """Append a string config option to a list"""

        value_str = args.pop(0)

        if value_str.lower() != 'none':
            if option in self._options:
                cast(List[str], self._options[option]).append(value_str)
            else:
                self._options[option] = [value_str]
        else:
            if option not in self._options:
                self._options[option] = []

    def _set_string_list(self, option: str, args: List[str]) -> None:
        """Set whitespace-separated string config options as a list"""

        if option not in self._options:
            if len(args) == 1 and args[0].lower() == 'none':
                self._options[option] = []
            else:
                self._options[option] = args[:]

        args.clear()

    def _append_string_list(self, option: str, args: List[str]) -> None:
        """Append whitespace-separated string config options to a list"""

        if option in self._options:
            cast(List[str], self._options[option]).extend(args)
        else:
            self._options[option] = args[:]

        args.clear()

    def _set_address_family(self, option: str, args: List[str]) -> None:
        """Set an address family config option"""

        value_str = args.pop(0).lower()

        if value_str == 'any':
            value = socket.AF_UNSPEC
        elif value_str == 'inet':
            value = socket.AF_INET
        elif value_str == 'inet6':
            value = socket.AF_INET6
        else:
            self._error(f'Invalid {option} value: {value_str}')

        if option not in self._options:
            self._options[option] = value

    def _set_canonicalize_host(self, option: str, args: List[str]) -> None:
        """Set a canonicalize host config option"""

        value_str = args.pop(0).lower()

        if value_str in ('yes', 'true'):
            value: Union[bool, str] = True
        elif value_str in ('no', 'false'):
            value = False
        elif value_str == 'always':
            value = value_str
        else:
            self._error(f'Invalid {option} value: {value_str}')

        if option not in self._options:
            self._options[option] = value

    def _set_rekey_limits(self, option: str, args: List[str]) -> None:
        """Set rekey limits config option"""

        byte_limit: Union[str, Tuple[()]] = args.pop(0).lower()

        if byte_limit == 'default':
            byte_limit = ()

        if args:
            time_limit: Optional[Union[str, Tuple[()]]] = args.pop(0).lower()

            if time_limit == 'none':
                time_limit = None
        else:
            time_limit = ()

        if option not in self._options:
            self._options[option] = byte_limit, time_limit

    def has_match_final(self) -> bool:
        """Return whether this config includes a 'Match final' block"""

        return self._final is not None

    def parse(self, path: Path) -> None:
        """Parse an OpenSSH config file and return matching declarations"""

        self._path = path
        self._line_no = 0
        self._matching = True
        self._tokens = {'%': '%'}

        logger.debug1('Reading config from "%s"', path)

        with open(path) as file:
            for line in file:
                self._line_no += 1

                line = line.strip()
                if not line or line[0] == '#':
                    continue

                try:
                    split_args = shlex.split(line)
                except ValueError as exc:
                    self._error(str(exc))

                args = []
                loption = ''
                allow_equal = True

                for i, arg in enumerate(split_args, 1):
                    if arg.startswith('='):
                        if len(arg) > 1:
                            args.append(arg[1:])
                    elif not allow_equal:
                        args.extend(split_args[i-1:])
                        break
                    elif arg.endswith('='):
                        args.append(arg[:-1])
                    elif '=' in arg:
                        arg, val = arg.split('=', 1)
                        args.append(arg)
                        args.append(val)
                    else:
                        args.append(arg)

                    if i == 1:
                        loption = args.pop(0).lower()
                        allow_equal = loption in self._conditionals

                if loption in self._no_split:
                    args = [line.lstrip()[len(loption):].strip()]

                if not self._matching and loption not in self._conditionals:
                    continue

                try:
                    option, handler = self._handlers[loption]
                except KeyError:
                    continue

                if not args:
                    self._error(f'Missing {option} value')

                handler(self, option, args)

                if args:
                    self._error(f'Extra data at end: {" ".join(args)}')

        self._set_tokens()

        for option in self._percent_expand:
            try:
                value = self._options[option]
            except KeyError:
                pass
            else:
                if isinstance(value, list):
                    value = [self._expand_val(item) for item in value]
                elif isinstance(value, str):
                    value = self._expand_val(value)

                self._options[option] = value

    def get_options(self, reload: bool) -> Dict[str, object]:
        """Return options to base a new config object on"""

        return self._last_options.copy() if reload else self._options.copy()

    @classmethod
    def load(cls, last_config: Optional['SSHConfig'],
             config_paths: ConfigPaths, reload: bool,
             canonical: bool, final: bool, *args: object) -> 'SSHConfig':
        """Load a list of OpenSSH config files into a config object"""

        config = cls(last_config, reload, canonical, final, *args)

        if config_paths:
            if isinstance(config_paths, (str, PurePath)):
                paths: Sequence[FilePath] = [config_paths]
            else:
                paths = config_paths

            for path in paths:
                config.parse(Path(path))

            config.loaded = True

        return config

    def get(self, option: str, default: object = None) -> object:
        """Get the value of a config option"""

        return self._options.get(option, default)

    def get_compression_algs(self) -> DefTuple[str]:
        """Return the compression algorithms to use"""

        compression = self.get('Compression')

        if compression is None:
            return ()
        elif compression:
            return 'zlib@openssh.com,zlib,none'
        else:
            return 'none,zlib@openssh.com,zlib'


class SSHClientConfig(SSHConfig):
    """Settings from an OpenSSH client config file"""

    _conditionals = {'host', 'match'}
    _no_split = {'proxycommand', 'remotecommand'}
    _percent_expand = {'CertificateFile', 'ForwardAgent', 'IdentityAgent',
                       'IdentityFile', 'ProxyCommand', 'RemoteCommand'}

    def __init__(self, last_config: 'SSHConfig', reload: bool,
                 canonical: bool, final: bool, local_user: str,
                 user: str, host: str, port: int) -> None:
        super().__init__(last_config, reload, canonical, final)

        self._local_user = local_user
        self._orig_host = host

        if user != ():
            self._options['User'] = user

        if port != ():
            self._options['Port'] = port

    def _match_val(self, match: str) -> object:
        """Return the value to match against in a match condition"""

        if match == 'host':
            return self._options.get('Hostname', self._orig_host)
        elif match == 'originalhost':
            return self._orig_host
        elif match == 'localuser':
            return self._local_user
        elif match == 'user':
            return self._options.get('User', self._local_user)
        elif match == 'tagged':
            return self._options.get('Tag', '')
        else:
            return None

    def _match_host(self, option: str, args: List[str]) -> None:
        """Begin a conditional block matching on host"""

        # pylint: disable=unused-argument

        pattern = ','.join(args)
        self._matching = WildcardPatternList(pattern).matches(self._orig_host)
        args.clear()

    def _set_hostname(self, option: str, args: List[str]) -> None:
        """Set hostname config option"""

        value = args.pop(0)

        if option not in self._options:
            self._tokens['h'] = \
                cast(str, self._options.get(option, self._orig_host))
            self._options[option] = self._expand_val(value)

    def _set_request_tty(self, option: str, args: List[str]) -> None:
        """Set a pseudo-terminal request config option"""

        value_str = args.pop(0).lower()

        if value_str in ('yes', 'true'):
            value: Union[bool, str] = True
        elif value_str in ('no', 'false'):
            value = False
        elif value_str in ('force', 'auto'):
            value = value_str
        else:
            self._error(f'Invalid {option} value: {value_str}')

        if option not in self._options:
            self._options[option] = value

    def _set_tokens(self) -> None:
        """Set the tokens available for percent expansion"""

        local_host = socket.gethostname()

        idx = local_host.find('.')
        short_local_host = local_host if idx < 0 else local_host[:idx]

        host = cast(str, self._options.get('Hostname', self._orig_host))
        port = str(self._options.get('Port', DEFAULT_PORT))
        user = cast(str, self._options.get('User') or self._local_user)
        home = os.path.expanduser('~')

        conn_info = ''.join((local_host, host, port, user))
        conn_hash = sha1(conn_info.encode('utf-8')).hexdigest()

        self._tokens.update({'C': conn_hash,
                             'h': host,
                             'L': short_local_host,
                             'l': local_host,
                             'n': self._orig_host,
                             'p': port,
                             'r': user,
                             'u': self._local_user})

        if home != '~':
            self._tokens['d'] = home

        if hasattr(os, 'getuid'):
            self._tokens['i'] = str(os.getuid())

    _handlers = {option.lower(): (option, handler) for option, handler in (
        ('Host',                            _match_host),
        ('Match',                           SSHConfig._match),
        ('Include',                         SSHConfig._include),

        ('AddressFamily',                   SSHConfig._set_address_family),
        ('BindAddress',                     SSHConfig._set_string),
        ('CanonicalDomains',                SSHConfig._set_string_list),
        ('CanonicalizeFallbackLocal',       SSHConfig._set_bool),
        ('CanonicalizeHostname',            SSHConfig._set_canonicalize_host),
        ('CanonicalizeMaxDots',             SSHConfig._set_int),
        ('CanonicalizePermittedCNAMEs',     SSHConfig._set_string_list),
        ('CASignatureAlgorithms',           SSHConfig._set_string),
        ('CertificateFile',                 SSHConfig._append_string),
        ('ChallengeResponseAuthentication', SSHConfig._set_bool),
        ('Ciphers',                         SSHConfig._set_string),
        ('Compression',                     SSHConfig._set_bool),
        ('ConnectTimeout',                  SSHConfig._set_int),
        ('EnableSSHKeySign',                SSHConfig._set_bool),
        ('ForwardAgent',                    SSHConfig._set_bool_or_str),
        ('ForwardX11Trusted',               SSHConfig._set_bool),
        ('GlobalKnownHostsFile',            SSHConfig._set_string_list),
        ('GSSAPIAuthentication',            SSHConfig._set_bool),
        ('GSSAPIDelegateCredentials',       SSHConfig._set_bool),
        ('GSSAPIKeyExchange',               SSHConfig._set_bool),
        ('HostbasedAuthentication',         SSHConfig._set_bool),
        ('HostKeyAlgorithms',               SSHConfig._set_string),
        ('Hostname',                        _set_hostname),
        ('HostKeyAlias',                    SSHConfig._set_string),
        ('IdentitiesOnly',                  SSHConfig._set_bool),
        ('IdentityAgent',                   SSHConfig._set_string),
        ('IdentityFile',                    SSHConfig._append_string),
        ('KbdInteractiveAuthentication',    SSHConfig._set_bool),
        ('KexAlgorithms',                   SSHConfig._set_string),
        ('MACs',                            SSHConfig._set_string),
        ('PasswordAuthentication',          SSHConfig._set_bool),
        ('PKCS11Provider',                  SSHConfig._set_string),
        ('PreferredAuthentications',        SSHConfig._set_string),
        ('Port',                            SSHConfig._set_int),
        ('ProxyCommand',                    SSHConfig._set_string),
        ('ProxyJump',                       SSHConfig._set_string),
        ('PubkeyAuthentication',            SSHConfig._set_bool),
        ('RekeyLimit',                      SSHConfig._set_rekey_limits),
        ('RemoteCommand',                   SSHConfig._set_string),
        ('RequestTTY',                      _set_request_tty),
        ('SendEnv',                         SSHConfig._append_string_list),
        ('ServerAliveCountMax',             SSHConfig._set_int),
        ('ServerAliveInterval',             SSHConfig._set_int),
        ('SetEnv',                          SSHConfig._set_string_list),
        ('Tag',                             SSHConfig._set_string),
        ('TCPKeepAlive',                    SSHConfig._set_bool),
        ('User',                            SSHConfig._set_string),
        ('UserKnownHostsFile',              SSHConfig._set_string_list)
    )}


class SSHServerConfig(SSHConfig):
    """Settings from an OpenSSH server config file"""

    def __init__(self, last_config: 'SSHConfig', reload: bool,
                 canonical: bool, final: bool, local_addr: str,
                 local_port: int, user: str, host: str, addr: str) -> None:
        super().__init__(last_config, reload, canonical, final)

        self._local_addr = local_addr
        self._local_port = local_port
        self._user = user
        self._host = host or addr
        self._addr = addr

    def _match_val(self, match: str) -> object:
        """Return the value to match against in a match condition"""

        if match == 'localaddress':
            return self._local_addr
        elif match == 'localport':
            return str(self._local_port)
        elif match == 'user':
            return self._user
        elif match == 'host':
            return self._host
        elif match == 'address':
            return self._addr
        else:
            return None

    def _set_tokens(self) -> None:
        """Set the tokens available for percent expansion"""

        self._tokens.update({'u': self._user})

    _handlers = {option.lower(): (option, handler) for option, handler in (
        ('Match',                           SSHConfig._match),
        ('Include',                         SSHConfig._include),

        ('AddressFamily',                   SSHConfig._set_address_family),
        ('AuthorizedKeysFile',              SSHConfig._set_string_list),
        ('AllowAgentForwarding',            SSHConfig._set_bool),
        ('BindAddress',                     SSHConfig._set_string),
        ('CanonicalDomains',                SSHConfig._set_string_list),
        ('CanonicalizeFallbackLocal',       SSHConfig._set_bool),
        ('CanonicalizeHostname',            SSHConfig._set_canonicalize_host),
        ('CanonicalizeMaxDots',             SSHConfig._set_int),
        ('CanonicalizePermittedCNAMEs',     SSHConfig._set_string_list),
        ('CASignatureAlgorithms',           SSHConfig._set_string),
        ('ChallengeResponseAuthentication', SSHConfig._set_bool),
        ('Ciphers',                         SSHConfig._set_string),
        ('ClientAliveCountMax',             SSHConfig._set_int),
        ('ClientAliveInterval',             SSHConfig._set_int),
        ('Compression',                     SSHConfig._set_bool),
        ('GSSAPIAuthentication',            SSHConfig._set_bool),
        ('GSSAPIKeyExchange',               SSHConfig._set_bool),
        ('HostbasedAuthentication',         SSHConfig._set_bool),
        ('HostCertificate',                 SSHConfig._append_string),
        ('HostKey',                         SSHConfig._append_string),
        ('KbdInteractiveAuthentication',    SSHConfig._set_bool),
        ('KexAlgorithms',                   SSHConfig._set_string),
        ('LoginGraceTime',                  SSHConfig._set_int),
        ('MACs',                            SSHConfig._set_string),
        ('PasswordAuthentication',          SSHConfig._set_bool),
        ('PermitTTY',                       SSHConfig._set_bool),
        ('Port',                            SSHConfig._set_int),
        ('PubkeyAuthentication',            SSHConfig._set_bool),
        ('RekeyLimit',                      SSHConfig._set_rekey_limits),
        ('TCPKeepAlive',                    SSHConfig._set_bool),
        ('UseDNS',                          SSHConfig._set_bool)
    )}
