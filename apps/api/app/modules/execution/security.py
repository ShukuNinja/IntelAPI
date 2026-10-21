import ipaddress
import socket
from urllib.parse import urlsplit

from fastapi import HTTPException


def validate_outbound_url(url: str) -> None:
    """Reject non-HTTP URLs and destinations resolving to non-public IP addresses.

    Redirects must remain disabled. DNS checks are defense in depth; production
    still needs network-level egress controls to mitigate DNS rebinding/TOCTOU.
    """
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Expected an absolute HTTP(S) URL.")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("URL credentials are not permitted.")
        host = parsed.hostname.rstrip(".").lower()

        blocked_hostnames = {
            "localhost",
            "localhost.localdomain",
            "metadata.google.internal",
        }

        if (
            host in blocked_hostnames
            or host.endswith(".localhost")
            or host.endswith(".local")
            or host.endswith(".internal")
        ):
            raise ValueError("Local destination is not allowed.")

        try:
            addresses = [ipaddress.ip_address(host)]
        except ValueError:
            answers = socket.getaddrinfo(
                host,
                parsed.port or (443 if parsed.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
            addresses = [ipaddress.ip_address(item[4][0].split("%", 1)[0]) for item in answers]
        if not addresses:
            raise ValueError("Host did not resolve.")
        for address in addresses:
            if (
                address.is_private
                or address.is_loopback
                or address.is_link_local
                or address.is_multicast
                or address.is_reserved
                or address.is_unspecified
            ):
                raise ValueError("Non-public destination address.")
    except (ValueError, OSError, socket.gaierror) as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "UNSAFE_DESTINATION",
                "message": "The outbound URL is invalid or not allowed.",
            },
        ) from exc
