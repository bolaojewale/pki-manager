# pki-manager

A PKI management tool that creates a local root Certificate Authority (CA) and Intermediate Certificate Authority for the purpose of creating and signing TLS certificates. This tool uses elliptic curve cryptography for certificates.

Available as both a **Bash script** (original) and a **Python MCP Server** for integration with AI assistants like Claude.

## Features

- Elliptic curve cryptography (ECC) support
- Root CA and Intermediate CA generation
- Service certificate generation and management
- Certificate expiration checking
- Automatic backup functionality
- Full & intermediate certificate chain creation
- Backup and offline root CA
- **MCP Server** for AI assistant integration (Claude Code, etc.)
- **Docker deployment** for persistent PKI server

## Prerequisites

### Bash Script
- OpenSSL 1.1.1 or later (3.0.0 or later recommended)
- Bash 4.0 or later (5.1.16 or later recommended)
- Basic understanding of PKI concepts

### Python MCP Server
- Python 3.11 or later
- Docker (optional, for containerized deployment)

## File Structure
```bash
├── pki-manager.sh           # Original Bash PKI management script
├── config.env.example       # Template for Bash script configuration
├── openssl.conf.example     # Template for OpenSSL configuration
│
├── pki_mcp_server/          # Python MCP server
│   ├── __init__.py
│   ├── __main__.py          # Entry point
│   ├── server.py            # FastMCP server + tool definitions
│   ├── config.py            # Pydantic configuration models
│   └── pki/                 # PKI operations
│       ├── ca.py            # Root/Intermediate CA operations
│       ├── certificates.py  # Leaf certificate generation
│       ├── chains.py        # Certificate chain management
│       └── backup.py        # Backup operations
│
├── tests/                   # Test suite
├── Dockerfile               # Container build
├── docker-compose.yml       # Easy local deployment
└── pyproject.toml           # Python project config
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/thecybergardener/pki-manager.git
cd pki-manager
```

2. Create your configuration:
```bash
cp config.env.example config.env
```

3. Make the script executable:
```bash
chmod u+x pki-manager.sh
```

## PKI Directory Structure

```
pki/
├── chains/          # Certificate chains
├── root/
│   ├── private/     # Root CA private key
│   ├── certs/       # Root CA certificate
│   ├── newcerts/    # Newly issued certificates
│   └── crl/         # Certificate revocation lists
├── intermediate/
│   ├── private/     # Intermediate CA private key
│   ├── certs/       # Intermediate CA certificate
│   ├── csr/         # Certificate signing requests
│   └── newcerts/    # Newly issued certificates
└── services/
    └── <service-name>/
        ├── private/ # Service private key
        ├── certs/   # Service certificate
        └── csr/     # Service CSR
```

## Configuration

Edit `config.env` to customize your PKI settings:

```bash
# Cryptographic settings
CURVE="prime256v1"  # Options: prime256v1, secp384r1, secp521r1

# Certificate validity periods (in days)
ROOT_VALIDITY=3560         # 10 years
INTERMEDIATE_VALIDITY=730  # 2 years
LEAF_VALIDITY=180          # 6 months
```

### Available Curves

- `prime256v1` (P-256): 128-bit security level, widely supported
- `secp384r1` (P-384): 192-bit security level, stronger security
- `secp521r1` (P-521): 256-bit security level, highest security

### Certificate Validity Peroids

Adjust the validity periods to your own preferences.

## Usage

### Initialize PKI Structure

Creates the PKI directory structure and generates root/intermediate CAs:
```bash
./pki-manager.sh init
```

### Generate Service Certificate

Creates a new certificate for a service:
```bash
./pki-manager.sh new-cert nginx example.com
```

### Check Certificate Expiration

Checks when all services certificate will expire:
```bash
./pki-manager.sh check 
```

Checks when a service's certificate will expire:
```bash
./pki-manager.sh check nginx
```

### Create Backup

Creates a backup of the PKI directory:
```bash
./pki-manager.sh backup
```

## Security Considerations

1. **Root CA Protection**
   - Keep the root CA offline when not in use
   - Store the root CA private key securely
   - Use the intermediate CA for day-to-day operations

2. **Private Keys**
   - All private keys are stored with 400 permissions (read-only for owner)
   - Private key directories have 700 permissions (accessible only by owner)

3. **Backups**
   - Regular backups are recommended
   - Backup private keys separately and securely
   - Keep backup media secure and offline

## Certificate Lifecycle Considerations

1. Monitor certificate expiration:
   - Script provides warnings 30 days before expiration
   - Plan renewals before expiration

## Best Practices

1. **Root CA Management**
   - Keep root CA offline when not in use
   - Use intermediate CA for routine operations
   - Secure root CA private key

2. **Service Certificates**
   - Use descriptive service names
   - Implement automatic renewal where possible
   - Monitor certificate expiration dates

3. **Backup Strategy**
   - Regular backups of the PKI directory
   - Secure storage of backup media
   - Test restore procedures periodically

## Troubleshooting

### Common Issues

1. **Permission Denied**
   ```bash
   chmod 700 pki/root/private
   chmod 400 pki/root/private/ca.key
   ```

2. **Configuration Not Found**
   - Ensure `config.env` exists in the same directory as the script
   - Check file permissions

3. **OpenSSL Errors**
   - Verify OpenSSL installation
   - Check OpenSSL version compatibility
   - Validate openssl.conf syntax
   ```bash
   openssl req -config openssl.conf -test
   ```

## MCP Server

The Python MCP (Model Context Protocol) server allows AI assistants like Claude to manage PKI operations directly.

### Installation

```bash
# Install from source
pip install .

# Or install with dev dependencies
pip install ".[dev]"
```

### Running the MCP Server

#### STDIO Transport (Local Development)

```bash
python -m pki_mcp_server
```

#### SSE Transport (Docker/Remote)

```bash
python -m pki_mcp_server --transport sse --port 8000
```

### Docker Deployment

```bash
# Build and run with Docker Compose
docker compose up -d

# View logs
docker compose logs -f
```

### Claude Code Integration

Add to your Claude Code MCP configuration:

**Remote Server (Docker)**
```json
{
  "mcpServers": {
    "pki-manager": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

**Local Development (STDIO)**
```json
{
  "mcpServers": {
    "pki-manager": {
      "command": "python",
      "args": ["-m", "pki_mcp_server"],
      "env": {
        "PKI_ROOT_DIR": "./pki",
        "PKI_ORGANIZATION": "MyOrg"
      }
    }
  }
}
```

### MCP Tools

| Tool | Description |
|------|-------------|
| `pki_init` | Initialize PKI with Root + Intermediate CA |
| `pki_new_cert` | Generate leaf certificate for a service |
| `pki_check` | Check certificate expiration |
| `pki_backup` | Backup PKI directory (excludes private keys) |
| `pki_offline_root` | Secure root CA key offline |
| `pki_status` | Get PKI status (initialized, root online/offline) |
| `pki_list_services` | List all services with certificates |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PKI_ROOT_DIR` | `pki` | Root directory for PKI files |
| `PKI_BACKUP_DIR` | `backups` | Directory for backups |
| `PKI_CURVE` | `prime256v1` | EC curve (prime256v1, secp384r1, secp521r1) |
| `PKI_ORGANIZATION` | `Home` | Organization name for certificates |
| `PKI_COUNTRY` | `US` | Two-letter country code |
| `PKI_STATE` | `State` | State or province |
| `PKI_LOCALITY` | `City` | City or locality |
| `PKI_ROOT_VALIDITY` | `1460` | Root CA validity (days) |
| `PKI_INTERMEDIATE_VALIDITY` | `730` | Intermediate CA validity (days) |
| `PKI_LEAF_VALIDITY` | `180` | Leaf certificate validity (days) |

### Running Tests

```bash
# Install dev dependencies
pip install ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=pki_mcp_server
```

## Future Planned Features

- Certificate Revocation (`pki_revoke_cert` tool)
- CRL (Certificate Revocation List) generation and distribution
- OCSP responder support
- n8n custom node integration

## License

This project is licensed under the MIT License - see the LICENSE file for details.
