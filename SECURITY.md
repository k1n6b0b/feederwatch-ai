# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 0.1.x   | ✓         |

## Reporting a Vulnerability

**Please do not report security vulnerabilities via public GitHub issues.**

Open a [private security advisory](https://github.com/k1n6b0b/feederwatch-ai/security/advisories/new) on GitHub. You'll receive a response within 48 hours.

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Scope

This add-on runs inside your Home Assistant instance on your local network and is not intended to be exposed to the public internet. Nevertheless, security matters:

- **Authentication**: The add-on relies on HA Ingress for authentication. Do not expose port 8099 directly.
- **MQTT credentials**: Stored in HA Add-on configuration (encrypted at rest by the Supervisor). Never committed to version control.
- **Model files**: Downloaded from GitHub Releases and Google CDN on first startup. Checksums are verified where published.
