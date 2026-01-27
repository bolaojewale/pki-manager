# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

pki-manager is a PKI management tool that creates and manages a local root Certificate Authority (CA) and Intermediate CA for generating TLS certificates. It uses elliptic curve cryptography (ECC) with configurable curves (prime256v1, secp384r1, secp521r1).

The project has two implementations:
1. **Bash Script** (`pki-manager.sh`) - Original standalone script using OpenSSL
2. **Python MCP Server** (`pki_mcp_server/`) - MCP server using the cryptography library

## Commands

### Bash Script

```bash
# Initialize PKI structure with Root CA and Intermediate CA
./pki-manager.sh init

# Generate new certificate for a service
./pki-manager.sh new-cert SERVICE DOMAIN [CSR-FILE] [ALTERNATE-NAMES...]

# Check certificate expiration (all services or specific one)
./pki-manager.sh check [SERVICE]

# Create backup of PKI directory
./pki-manager.sh backup

# Move root CA key offline (secure storage)
./pki-manager.sh offline-root PATH

# Show help
./pki-manager.sh help
```

### Python MCP Server

```bash
# Install dependencies
pip install .

# Run MCP server (STDIO transport for local development)
python -m pki_mcp_server

# Run MCP server (SSE transport for Docker/remote)
python -m pki_mcp_server --transport sse --port 8000

# Run tests
pip install ".[dev]"
pytest

# Docker deployment
docker compose up -d
```

## Architecture

### Bash Script (pki-manager.sh)

The script follows a function-based architecture with strict error handling (`set -euo pipefail`):

1. **Logging**: `log()` and `error()` functions for timestamped console/file output
2. **Configuration**: `validate_config()` loads and validates `config.env`
3. **PKI Setup**: `create_directory_structure()`, `check_existing_pki()`, `create_cert_chain()`
4. **CA Management**: `generate_root_ca()`, `generate_intermediate_ca()`, `offline_root_ca()`
5. **Certificate Generation**: `generate_leaf_cert()`, `sign_csr()`, `format_san()`, `create_temp_config()`
6. **Operations**: `check_expiration()`, `list_services()`, `backup_pki()`

### Python MCP Server (pki_mcp_server/)

```
pki_mcp_server/
├── __init__.py
├── __main__.py           # CLI entry point with argparse
├── server.py             # FastMCP server + 7 tool definitions
├── config.py             # Pydantic configuration with PKI_* env vars
├── exceptions.py         # Custom exceptions (PKIError hierarchy)
├── logging_config.py     # Logging setup
└── pki/
    ├── ca.py             # CAManager - Root/Intermediate CA operations
    ├── certificates.py   # CertificateManager - Leaf cert generation
    ├── chains.py         # ChainManager - Certificate chain files
    └── backup.py         # BackupManager - Backup operations
```

**Key Classes:**
- `CAManager` (`pki/ca.py`): Root/Intermediate CA generation, key/cert persistence, secure deletion
- `CertificateManager` (`pki/certificates.py`): Leaf certificate generation, SAN parsing, expiration checks
- `ChainManager` (`pki/chains.py`): Certificate chain file creation
- `BackupManager` (`pki/backup.py`): Backup creation (excludes private keys by default)

**MCP Tools (defined in `server.py`):**
| Tool | Purpose | Destructive |
|------|---------|-------------|
| `pki_init` | Initialize PKI with Root + Intermediate CA | Yes (requires confirmation if exists) |
| `pki_new_cert` | Generate leaf certificate for a service | No |
| `pki_check` | Check certificate expiration | No |
| `pki_backup` | Backup PKI directory | No |
| `pki_offline_root` | Secure root CA key offline | Yes (requires confirmation) |
| `pki_status` | Get PKI status | No |
| `pki_list_services` | List all services with certificates | No |

### PKI Directory Structure (created by `init`)

```
pki/
├── root/                    # Root CA (offline after setup)
│   ├── private/            # Root private key (mode 700)
│   ├── certs/              # Root certificate
│   └── ...
├── intermediate/           # Intermediate CA (daily operations)
│   ├── private/            # Intermediate private key
│   ├── certs/              # Intermediate certificate
│   ├── csr/                # Certificate signing requests
│   └── ...
├── services/<name>/        # Per-service certificates
│   ├── private/
│   ├── certs/
│   ├── csr/
│   └── chains/
└── chains/                 # Global certificate chains
```

### Configuration

**Bash Script**: Uses `config.env` (copy from `config.env.example`)

**Python MCP Server**: Uses environment variables with `PKI_` prefix:
- `PKI_ROOT_DIR` - PKI directory (default: `pki`)
- `PKI_BACKUP_DIR` - Backup directory (default: `backups`)
- `PKI_CURVE` - EC curve (default: `prime256v1`)
- `PKI_ORGANIZATION` - Organization name (default: `Home`)
- `PKI_ROOT_VALIDITY` - Root CA validity in days (default: `1460`)
- `PKI_INTERMEDIATE_VALIDITY` - Intermediate CA validity (default: `730`)
- `PKI_LEAF_VALIDITY` - Leaf cert validity (default: `180`)

## Security Model

- Root CA key kept offline via `offline-root` / `pki_offline_root` command
- Secure deletion: overwrites 3x with random data before unlink (Python) or `shred -u` (Bash)
- Private keys: mode 0o400 (read-only owner)
- Private directories: mode 0o700 (owner-only)
- Intermediate CA used for day-to-day certificate signing
- SHA-384 digest algorithm throughout
- Destructive MCP operations require `confirm_destructive=true`

## Future Work

- `pki_revoke_cert` tool - Certificate revocation
- CRL (Certificate Revocation List) generation and distribution
- OCSP responder support
- n8n custom node integration
