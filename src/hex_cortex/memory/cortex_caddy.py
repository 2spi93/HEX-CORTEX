from __future__ import annotations

from urllib.parse import urlparse


def render_cortex_caddyfile(profile: dict[str, object]) -> str:
    if profile.get("service_allowed") is not True:
        raise ValueError("service profile must be allowed")
    public_url = str(profile["public_base_url"])
    host = urlparse(public_url).hostname
    port = int(profile["app_port"])
    body_limit = int(profile.get("request_body_limit_mb", 2))
    return "\n".join(
        [
            f"{host} {{",
            "    encode zstd gzip",
            "    request_body {",
            f"        max_size {body_limit}MB",
            "    }",
            "    header {",
            "        Strict-Transport-Security \"max-age=31536000; includeSubDomains\"",
            "        X-Content-Type-Options \"nosniff\"",
            "        X-Frame-Options \"DENY\"",
            "        Referrer-Policy \"no-referrer\"",
            "    }",
            f"    reverse_proxy 127.0.0.1:{port}",
            "}",
            "",
        ]
    )
