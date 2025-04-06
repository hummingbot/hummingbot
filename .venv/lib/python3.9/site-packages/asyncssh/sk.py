# Copyright (c) 2019-2024 by Ron Frederick <ronf@timeheart.net> and others.
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

"""U2F security key handler"""

from base64 import urlsafe_b64encode
import ctypes
from hashlib import sha256
import hmac
import time
from typing import Callable, List, Mapping, NoReturn, Optional
from typing import Sequence, Tuple, TypeVar, cast


_PollResult = TypeVar('_PollResult')
_SKResidentKey = Tuple[int, str, bytes, bytes]


_CTAP1_POLL_INTERVAL = 0.1

_dummy_hash = 32 * b'\0'

# Flags
SSH_SK_USER_PRESENCE_REQD = 0x01

# Algorithms
SSH_SK_ECDSA = -7
SSH_SK_ED25519 = -8


def _decode_public_key(alg: int, public_key: Mapping[int, object]) -> bytes:
    """Decode algorithm and public value from a CTAP public key"""

    result = cast(bytes, public_key[-2])

    if alg == SSH_SK_ED25519:
        return  result
    else:
        return  b'\x04' + result + cast(bytes, public_key[-3])


def _verify_rp_id(_rp_id: str, _origin: str):
    """Allow any relying party name -- SSH encodes the application here"""

    return True


def _ctap1_poll(poll_interval: float, func: Callable[..., _PollResult],
                *args: object) -> _PollResult:
    """Poll until a CTAP1 response is received"""

    while True:
        try:
            return func(*args)
        except ApduError as exc:
            if exc.code != APDU.USE_NOT_SATISFIED:
                raise

            time.sleep(poll_interval)


def _ctap1_enroll(dev: 'CtapHidDevice', alg: int,
                  application: str) -> Tuple[bytes, bytes]:
    """Enroll a new security key using CTAP version 1"""

    ctap1 = Ctap1(dev)

    if alg != SSH_SK_ECDSA:
        raise ValueError('Unsupported algorithm')

    app_hash = sha256(application.encode('utf-8')).digest()
    registration = _ctap1_poll(_CTAP1_POLL_INTERVAL, ctap1.register,
                               _dummy_hash, app_hash)

    return registration.public_key, registration.key_handle


def _ctap2_enroll(dev: 'CtapHidDevice', alg: int, application: str,
                  user: str, pin: Optional[str],
                  resident: bool) -> Tuple[bytes, bytes]:
    """Enroll a new security key using CTAP version 2"""

    ctap2 = Ctap2(dev)

    rp = {'id': application, 'name': application}
    user_cred = {'id': user.encode('utf-8'), 'name': user}
    key_params = [{'type': 'public-key', 'alg': alg}]
    options = {'rk': resident}

    pin_protocol: Optional[PinProtocolV1]
    pin_auth: Optional[bytes]

    if pin:
        pin_protocol = PinProtocolV1()
        pin_token = ClientPin(ctap2, pin_protocol).get_pin_token(pin)
        pin_auth = hmac.new(pin_token, _dummy_hash, sha256).digest()[:16]
    else:
        pin_protocol = None
        pin_auth = None

    pin_version = pin_protocol.VERSION if pin_protocol else None
    cred = ctap2.make_credential(_dummy_hash, rp, user_cred, key_params,
                                 options=options, pin_uv_param=pin_auth,
                                 pin_uv_protocol=pin_version)
    cdata = cred.auth_data.credential_data

    # pylint: disable=no-member
    return _decode_public_key(alg, cdata.public_key), cdata.credential_id


def _win_enroll(alg: int, application: str, user: str) -> Tuple[bytes, bytes]:
    """Enroll a new security key using Windows WebAuthn API"""

    client = WindowsClient(application, verify=_verify_rp_id)

    rp = {'id': application, 'name': application}
    user_cred = {'id': user.encode('utf-8'), 'name': user}
    key_params = [{'type': 'public-key', 'alg': alg}]
    options = {'rp': rp, 'user': user_cred, 'challenge': b'',
               'pubKeyCredParams': key_params}

    result = client.make_credential(options)
    cdata = result.attestation_object.auth_data.credential_data

    # pylint: disable=no-member
    return _decode_public_key(alg, cdata.public_key), cdata.credential_id


def _ctap1_sign(dev: 'CtapHidDevice', message_hash: bytes, application: str,
                key_handle: bytes) -> Tuple[int, int, bytes]:
    """Sign a message with a security key using CTAP version 1"""

    ctap1 = Ctap1(dev)

    app_hash = sha256(application.encode('utf-8')).digest()

    auth_response = _ctap1_poll(_CTAP1_POLL_INTERVAL, ctap1.authenticate,
                                message_hash, app_hash, key_handle)

    flags = auth_response[0]
    counter = int.from_bytes(auth_response[1:5], 'big')
    sig = auth_response[5:]

    return flags, counter, sig


def _ctap2_sign(dev: 'CtapHidDevice', message_hash: bytes,
                application: str, key_handle: bytes,
                touch_required: bool) -> Tuple[int, int, bytes]:
    """Sign a message with a security key using CTAP version 2"""

    ctap2 = Ctap2(dev)

    allow_creds = [{'type': 'public-key', 'id': key_handle}]
    options = {'up': touch_required}

    # See if key handle exists before requiring touch
    if touch_required:
        ctap2.get_assertions(application, message_hash, allow_creds,
                             options={'up': False})

    assertion = ctap2.get_assertions(application, message_hash, allow_creds,
                                     options=options)[0]

    auth_data = assertion.auth_data

    return auth_data.flags, auth_data.counter, assertion.signature


def _win_sign(data: bytes, application: str,
              key_handle: bytes) -> Tuple[int, int, bytes, bytes]:
    """Sign a message with a security key using Windows WebAuthn API"""

    client = WindowsClient(application, verify=_verify_rp_id)

    creds = [{'type': 'public-key', 'id': key_handle}]
    options = {'challenge': data, 'rpId': application,
               'allowCredentials': creds}

    result = client.get_assertion(options).get_response(0)
    auth_data = result.authenticator_data

    return auth_data.flags, auth_data.counter, \
           result.signature, bytes(result.client_data)


def sk_webauthn_prefix(data: bytes, application: str) -> bytes:
    """Calculate a WebAuthn request prefix"""

    return b'{"type":"webauthn.get","challenge":"' + \
           urlsafe_b64encode(data).rstrip(b'=') + b'","origin":"' + \
           application.encode('utf-8') + b'"'


def sk_enroll(alg: int, application: str, user: str, pin: Optional[str],
              resident: bool) -> Tuple[bytes, bytes]:
    """Enroll a new security key"""

    if sk_use_webauthn:
        return _win_enroll(alg, application, user)

    try:
        dev = next(CtapHidDevice.list_devices())
    except StopIteration:
        raise ValueError('No security key found') from None

    try:
        return _ctap2_enroll(dev, alg, application, user, pin, resident)
    except CtapError as exc:
        if exc.code == CtapError.ERR.PUAT_REQUIRED:
            raise ValueError('PIN required') from None
        elif exc.code == CtapError.ERR.PIN_INVALID:
            raise ValueError('Invalid PIN') from None
        else:
            raise ValueError(str(exc)) from None
    except ValueError:
        try:
            return _ctap1_enroll(dev, alg, application)
        except ApduError as exc:
            raise ValueError(str(exc)) from None
    finally:
        dev.close()


def sk_sign(data: bytes, application: str, key_handle: bytes, flags: int,
            is_webauthn: bool = False) -> Tuple[int, int, bytes, bytes]:
    """Sign a message with a security key"""

    touch_required = bool(flags & SSH_SK_USER_PRESENCE_REQD)

    if is_webauthn and sk_use_webauthn:
        return _win_sign(data, application, key_handle)

    if is_webauthn:
        data = sk_webauthn_prefix(data, application) + b'}'

    message_hash = sha256(data).digest()

    for dev in CtapHidDevice.list_devices():
        try:
            flags, counter, sig = _ctap2_sign(dev, message_hash, application,
                                              key_handle, touch_required)

            return flags, counter, sig, data
        except CtapError as exc:
            if exc.code != CtapError.ERR.NO_CREDENTIALS:
                raise ValueError(str(exc)) from None
        except ValueError:
            try:
                flags, counter, sig = _ctap1_sign(dev, message_hash,
                                                  application, key_handle)

                return flags, counter, sig, data
            except ApduError as exc:
                if exc.code != APDU.WRONG_DATA:
                    raise ValueError(str(exc)) from None
        finally:
            dev.close()

    raise ValueError('Security key credential not found')


def sk_get_resident(application: str, user: Optional[str],
                    pin: str) -> Sequence[_SKResidentKey]:
    """Get keys resident on a security key"""

    app_hash = sha256(application.encode('utf-8')).digest()
    result: List[_SKResidentKey] = []

    for dev in CtapHidDevice.list_devices():
        try:
            ctap2 = Ctap2(dev)

            pin_protocol = PinProtocolV1()
            pin_token = ClientPin(ctap2, pin_protocol).get_pin_token(pin)
            cred_mgmt = CredentialManagement(ctap2, pin_protocol, pin_token)

            for cred in cred_mgmt.enumerate_creds(app_hash):
                user_info = cast(Mapping[str, object],
                                 cred[CredentialManagement.RESULT.USER])
                name = cast(str, user_info['name'])

                if user and name != user:
                    continue

                cred_id = cast(Mapping[str, object],
                               cred[CredentialManagement.RESULT.CREDENTIAL_ID])
                key_handle = cast(bytes, cred_id['id'])

                public_key = cast(Mapping[int, object],
                                  cred[CredentialManagement.RESULT.PUBLIC_KEY])

                alg = cast(int, public_key[3])
                public_value = _decode_public_key(alg, public_key)

                result.append((alg, name, public_value, key_handle))
        except CtapError as exc:
            if exc.code == CtapError.ERR.NO_CREDENTIALS:
                continue
            elif exc.code == CtapError.ERR.PIN_INVALID:
                raise ValueError('Invalid PIN') from None
            elif exc.code == CtapError.ERR.PIN_NOT_SET:
                raise ValueError('PIN not set') from None
            else:
                raise ValueError(str(exc)) from None
        finally:
            dev.close()

    return result


try:
    from fido2.client import WindowsClient
    from fido2.ctap import CtapError
    from fido2.ctap1 import Ctap1, APDU, ApduError
    from fido2.ctap2 import Ctap2, ClientPin, PinProtocolV1
    from fido2.ctap2 import CredentialManagement
    from fido2.hid import CtapHidDevice

    sk_available = True

    sk_use_webauthn = WindowsClient.is_available() and \
                      hasattr(ctypes, 'windll') and \
                      not ctypes.windll.shell32.IsUserAnAdmin()
except (ImportError, OSError, AttributeError): # pragma: no cover
    sk_available = False
    sk_use_webauthn = False

    def _sk_not_available(*args: object, **kwargs: object) -> NoReturn:
        """Report that security key support is unavailable"""

        raise ValueError('Security key support not available')

    sk_enroll = _sk_not_available
    sk_sign = _sk_not_available
    sk_get_resident = _sk_not_available
