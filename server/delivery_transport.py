#!/usr/bin/env python3
"""One-shot bounded HTTP delivery child.

No imported PBT server state, lead database, logging, or credentials on argv.
Linux parent-death SIGKILL prevents orphaned slow network requests after the
server is killed. The parent enforces a separate absolute wall-clock deadline.
Exit 0=2xx, 10=permanent HTTP 4xx, 11=transient, 12=protocol failure.
"""
import base64
import ctypes
import json
import math
import os
import signal
import sys
import urllib.error
import urllib.request
from urllib.parse import urlsplit


def parent_death_guard():
    """PR_SET_PDEATHSIG is set *inside* the child, never in a fork preexec."""
    if sys.platform != 'linux':
        return False
    try:
        expected = int(os.environ.get('PBT_PARENT_PID', '0'))
        if expected < 2:
            return False
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
            return False
        # Parent may have died between Popen and prctl.
        return os.getppid() == expected
    except (OSError, ValueError, AttributeError):
        return False


class RejectRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward HMAC headers or Telegram credentials.


def main():
    if not parent_death_guard():
        return 12
    try:
        payload = sys.stdin.buffer.read(65537)
        if len(payload) > 65536:
            return 12
        request = json.loads(payload)
        url = request['url']
        headers = request['headers']
        timeout = request['socket_timeout_s']
        if not isinstance(url, str) or not isinstance(headers, dict):
            return 12
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            return 12
        if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0.1 <= timeout <= 120:
            return 12
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in headers.items()):
            return 12
        raw = base64.b64decode(request['body_b64'], validate=True)
        if len(raw) > 16384:
            return 12
    except (ValueError, KeyError, TypeError, UnicodeError):
        return 12

    try:
        opener = urllib.request.build_opener(RejectRedirect)
        with opener.open(urllib.request.Request(url, raw, headers), timeout=timeout) as response:
            if 200 <= response.status < 300:
                return 0  # Headers-only acknowledgement; never consume a trickled 2xx body.
            sys.stdout.write(f'HTTP {response.status}')
            return 11
    except urllib.error.HTTPError as exc:
        sys.stdout.write(f'HTTP {exc.code}')
        return 10 if 400 <= exc.code < 500 and exc.code not in (408, 429) else 11
    except Exception as exc:
        # Only the type name is emitted; error messages may contain URLs/tokens.
        sys.stdout.write(type(exc).__name__)
        return 11


if __name__ == '__main__':
    sys.exit(main())
