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

### CA File Naming and OpenSSL Environment Variables

The root and intermediate CA `.key`, `.crt`, and `.csr` files are **named after
their CommonName**, lowercased with spaces replaced by dashes. For example:

```bash
ROOT_CN="Root CA"           # -> pki/root/certs/root-ca.crt
INTERMEDIATE_CN="Intermediate CA"  # -> .../intermediate-ca.crt
```

Because those filenames are not known until `config.env` is read, `openssl.conf`
locates the CA key/cert through environment variables instead of hardcoded
paths (`private_key = $ENV::ROOT_CA_KEY`, `certificate = $ENV::ROOT_CA_CERT`,
and the intermediate equivalents). `pki-manager.sh` exports these on every run,
so all script commands work without any extra steps:

| Variable | Points to |
|----------|-----------|
| `ROOT_CA_KEY`          | Root CA private key |
| `ROOT_CA_CERT`         | Root CA certificate |
| `INTERMEDIATE_CA_KEY`  | Intermediate CA private key |
| `INTERMEDIATE_CA_CERT` | Intermediate CA certificate |

> **Running OpenSSL by hand:** if you invoke `openssl ca ...` directly against
> `openssl.conf` (outside the script), you must export these four variables
> first, or OpenSSL fails with `variable has no value`:
>
> ```bash
> export ROOT_CA_KEY="pki/root/private/root-ca.key"
> export ROOT_CA_CERT="pki/root/certs/root-ca.crt"
> export INTERMEDIATE_CA_KEY="pki/intermediate/private/intermediate-ca.key"
> export INTERMEDIATE_CA_CERT="pki/intermediate/certs/intermediate-ca.crt"
> ```

## Usage

### Initialize PKI Structure

Creates the PKI directory structure and generates root/intermediate CAs:
```bash
./pki-manager.sh init
```

### Install Root Certificate
The cert you want to install in your machines' trust stores is the root CA certificate:

pki/root/certs/root-ca.crt

Why the root, not the intermediate. This is a two-tier PKI:

Root CA (root-ca.crt)  ──signs──►  Intermediate CA (intermediate-ca.crt)  ──signs──►  service certs

A client trusts a service cert if it can build a chain from the service cert up to a CA it already trusts. If you
install the root, the client can validate the whole chain (root → intermediate → service). That's the one cert you
distribute, and it covers every cert your PKI will ever issue — including future intermediates if you rotate them.

If you installed the intermediate instead, you'd have to redistribute it every time the intermediate rotates (yours is
set to a 2-year validity), so the root is the right anchor.

The other half: serve the chain

Installing the root is necessary but not sufficient. Each service must present its leaf cert + the intermediate so the
client can link the service cert back to the trusted root. Clients don't fetch the intermediate on their own here.
That's what this file is for:

pki/chains/intermediate-chain.crt

Configure the service (nginx, etc.) to serve that chain as its certificate file. Do not put the root in the served
chain — the client already has it.

Installing the root CA on clients

- Linux (Debian/Ubuntu): copy root-ca.crt to /usr/local/share/ca-certificates/root-ca.crt, then sudo
update-ca-certificates
- Linux (RHEL/Fedora): copy to /etc/pki/ca-trust/source/anchors/, then sudo update-ca-trust
- macOS: sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain root-ca.crt
- Windows: certutil -addstore -f Root root-ca.crt (as admin), or import into "Trusted Root Certification Authorities" via
certmgr
- Browsers: Firefox uses its own store (Settings → Certificates → Authorities → Import); Chrome/Edge use the OS store

One caveat: distribute only the certificate (root-ca.crt) — never the root's private key (pki/root/private/). The cert is
public and safe to push everywhere; the key must stay offline.

root/newcerts/1000.pem is the Intermediate CA certificate, not a service cert:

subject = CN=Intermediate CA   (O=Home)
issuer  = CN=Root CA           (the root signed it)
valid   = Jun 5 2026  →  Jun 4 2028   (your 2-year INTERMEDIATE_VALIDITY)

This is normal and expected. When you run init, the root CA signs the intermediate, and OpenSSL's CA database copies
every cert the root issues into root/newcerts/<serial>.pem. Serial 1000 is the first thing the root ever signed — your
intermediate. The matching ledger entry confirms it:

root/index.txt:  V  280604104643Z  1000  unknown  /CN=Intermediate CA

(V = valid, serial 1000, the intermediate.)

1000.pem is a copy of intermediate-ca.crt, produced as a byproduct of signing. Let me prove it:

● Bash(echo "=== fingerprint: intermediate/certs/intermediate-ca.crt ===" && openssl x509 -in
   intermediate/certs/intermediate-ca.crt -noout -fingerprint -sha256 2>/dev/null;…)
⎿  === fingerprint: intermediate/certs/intermediate-ca.crt ===
   sha256 Fingerprint=3E:6C:46:92:05:FB:3E:F1:E4:9D:60:67:23:78:C1:06:CB:E5:47:9D:8B:62:C6:85:2F:9F:34:1A:95:F4:6
   9:8A
   … +3 lines (ctrl+o to expand)

● Identical fingerprints — they're the same certificate. 1000.pem did not create anything; it's an archived copy of
intermediate-ca.crt.

The actual order of operations during init

1. Generate intermediate-ca.key        ← a fresh private key, made first
2. Build a CSR from intermediate-ca.key ← "please sign me, CN=Intermediate CA"
3. Root CA signs the CSR             ← root uses ITS key (root/private/root-ca.key)
4. Output written to TWO places at once:
      → intermediate/certs/intermediate-ca.crt   (the working copy you use)
      → root/newcerts/1000.pem                (the root's archive copy)

So the dependency runs the opposite way from what you asked:

- intermediate-ca.key is generated independently, first. Nothing creates it from 1000.pem.
- intermediate-ca.crt and 1000.pem are byte-for-byte the same file — both are the output of step 3.

Why two copies exist

root/newcerts/1000.pem is part of the root CA's bookkeeping, not something services use. Every time the root signs
anything, OpenSSL files a copy under newcerts/<serial>.pem and logs a line in root/index.txt. It's the root's
permanent record of "I issued this cert, serial 1000." You could delete root/newcerts/ and your PKI would still
function — intermediate-ca.crt is the copy that actually gets used in chains.

Think of it as: the key is the secret (intermediate-ca.key), the crt is the signed public document, and 1000.pem is the
registrar's filed duplicate of that document.

-
---
  The big picture

  You're building a chain of trust. The goal is that a browser or client, presented with nginx.example.com's
  certificate, can mathematically prove it traces back to something it already trusts — your Root CA. The chain is:

  Root CA  ──signs──►  Intermediate CA  ──signs──►  Service certs (nginx, etc.)
  (trust anchor)       (daily workhorse)            (leaf certs)

  Each arrow is a digital signature: the issuer hashes the subject's certificate and encrypts that hash with the
  issuer's private key. Anyone with the issuer's public cert can verify it. That's the entire mechanism.

  ---
  Step 1 — init builds the structure (pki-manager.sh:507)

  init runs four functions in order. Walking each:

  1a. create_directory_structure (line 201)

  Creates root/ and intermediate/ each with private/ certs/ csr/ newcerts/ crl/, locks the private/ dirs to 700, and
  seeds two bookkeeping files per CA:
  - index.txt — the CA's ledger; every cert it signs gets a line here.
  - serial — the next serial number, starting at 1000. (This is why your intermediate is 1000.pem.)

  These two files are what make OpenSSL's ca command behave like a real CA with a database, rather than just signing
  blindly.

  1b. generate_root_ca (line 235)

  openssl ecparam -genkey -name prime256v1 -out root/private/root-ca.key   # the secret
  openssl req -new -x509 -days 3560 -extensions v3_ca ...             # self-signed cert
  Two outputs:
  - root-ca.key — the root private key. The crown jewels. Whoever has this is your CA.
  - root-ca.crt — the root certificate. It's self-signed (issuer == subject == "Root CA") because there's nothing above it.
  -extensions v3_ca stamps it CA:TRUE, meaning "this cert is allowed to sign other certs." This is the file you install
  on your computers.

  1c. generate_intermediate_ca (line 247)

  This is the three-move dance you asked about earlier:
  openssl ecparam -genkey ... -out intermediate/private/intermediate-ca.key   # 1. new key
  openssl req -new -key intermediate-ca.key -out intermediate-ca.csr ...         # 2. CSR (a request)
  openssl ca -name root_ca -extensions v3_intermediate_ca -in ...csr \     # 3. root signs it
     -out intermediate/certs/intermediate-ca.crt
  - The CSR (Certificate Signing Request) is the intermediate saying "here's my public key and my name (CN=Intermediate
  CA) — please vouch for me." It's not a cert; it's an application.
  - The openssl ca step is the root reviewing and signing that application. This is the moment that:
    - writes intermediate-ca.crt (your working copy),
    - writes the identical root/newcerts/1000.pem (the root's archive — the duplicate you saw),
    - records a line in root/index.txt,
    - bumps root/serial to 1001.

  The intermediate is also CA:TRUE (via v3_intermediate_ca), so it can sign things too — but it's typically CA:TRUE with
  a pathlen:0 constraint, meaning "I can sign leaf certs but no further sub-CAs."

  1d. create_cert_chain (line 134)

  Bundles certs into ready-to-use files in chains/:
  cat intermediate-ca.crt root-ca.crt  >  ca-chain.crt          # full chain
  cp  intermediate-ca.crt           >  intermediate-chain.crt # just intermediate
  These exist so you don't have to assemble chains by hand later.

  ---
  Step 2 — distribute the trust anchor (the question you started with)

  Install root/certs/root-ca.crt into every client's OS/browser trust store. Now those machines trust anything your PKI
  signs, forever (until the root's 10-year validity expires). You do this once per machine.

  You never distribute root-ca.key. Public cert out to the world; private key stays locked down.

  ---
  Step 3 — new-cert issues a service certificate (pki-manager.sh:526 → generate_leaf_cert line 356)

  When you run ./pki-manager.sh new-cert nginx example.com:

  # 1. fresh key for this service
  openssl ecparam -genkey ... -out services/nginx/private/nginx.key

  # 2. CSR for CN=example.com
  openssl req -new -key nginx.key -out services/nginx/csr/nginx.csr -subj ".../CN=example.com"

  # 3. the INTERMEDIATE signs it (note: -name intermediate_ca, not root_ca)
  openssl ca -name intermediate_ca -extensions server_cert -days 180 \
     -in nginx.csr -out services/nginx/certs/nginx.crt

  Key points:
  - The intermediate signs leaf certs, not the root. That's why a service cert's record lands in intermediate/index.txt
  and intermediate/newcerts/, not root's. (This is exactly why your intermediate/newcerts/ is empty — you haven't issued
  a service cert yet.)
  - -extensions server_cert stamps it CA:FALSE + extendedKeyUsage=serverAuth — i.e. "this is an end TLS server cert, it
  cannot sign anything." That distinction is what stops a leaked service cert from becoming a rogue CA.
  - SANs (Subject Alternative Names): if you pass extra names/IPs, format_san (line 264) + create_temp_config (line 284)
  build a temp config adding subjectAltName = DNS:...,IP:.... Modern browsers ignore CN and require SANs, so for real
  use, always pass the domain(s) as SANs:
  ./pki-manager.sh new-cert nginx example.com www.example.com 192.168.1.10

  3b. create_service_chain (line 156)

  cat nginx.crt intermediate-ca.crt > services/nginx/chains/nginx-chain.crt
  This leaf + intermediate bundle is what you hand to nginx. It deliberately omits the root — the client already has the
  root installed (Step 2), and a server shouldn't send its own trust anchor.

  ---
  Step 4 — how validation actually works at connect time

  Client connects to nginx. nginx presents nginx-chain.crt (leaf + intermediate). The client then:

  1. Reads the leaf → "issued by Intermediate CA." Verifies the intermediate's signature on it. ✓
  2. Reads the intermediate → "issued by Root CA." Verifies the root's signature on it. ✓
  3. Looks for "Root CA" in its trust store → finds it (because you did Step 2). ✓
  4. Checks each cert is in date, not revoked, and the hostname matches a SAN. ✓

  All four pass → green padlock. Remove any link (don't install the root, or don't serve the intermediate) and the chain
  breaks.

  ---
  Step 5 — operational lifecycle

  - offline-root PATH (line 70): backs up the root key/cert + ledger to an encrypted tarball with checksums, then shreds
  root-ca.key off disk. This is best practice: an attacker can't steal a key that isn't there. You only restore it from
  backup on the rare occasion you need to issue a new intermediate. The intermediate stays online for daily new-cert
  work.
  - check [service] (line 436): reads each cert's notAfter and warns under 30 days. Your validities — root 10yr,
  intermediate 2yr, leaf 6mo — mean leaves rotate often (good; limits blast radius) and you re-issue them with new-cert
  before expiry.
  - backup (line 214): tars the whole PKI excluding private/, so you can archive structure/ledgers without exposing
  keys.

  ---
  The one-paragraph version

  init makes a self-signed Root CA (root-ca.crt — install this everywhere), which signs an Intermediate CA (intermediate-ca.crt
  — the duplicate you found at root/newcerts/1000.pem). Day to day, new-cert has the intermediate sign short-lived
  service certs, bundled with the intermediate as a chain you feed to nginx. Clients trust those services because the
  chain leads back to the root they already have installed. Then you take the root offline and rotate leaves as they
  expire.

---
I created a service cert for my proxmox server. the proxmox interface is asking for a private key (optional) and a
  certificate chain. what should be included in the certificate chain? why is the key optional? when should I upload
  it. dont make the answer too wordy

● Certificate chain field: your leaf cert + the intermediate, in that order — leaf on top. That's exactly the file your
  script made:

  pki/services/<service>/chains/<service>-chain.crt

  Do not include the root. Proxmox serves this to clients; clients already trust the root (you installed it), so the
  root in the chain is redundant.

  Why the key is "optional": the field is optional in general because Proxmox sometimes already holds the matching
  private key (e.g. it generated the keypair itself). It only needs whatever it doesn't already have.

  When you must upload it: in your case, you do — your script generated the key
  (pki/services/<service>/private/<service>.key), so Proxmox has never seen it. A cert is useless without its matching
  private key, so upload both: the chain file and <service>.key. After upload, Proxmox restarts pveproxy and serves the
  new cert.

  One check before you upload: make sure the cert's SAN includes the hostname/IP you use to reach the web UI, or
  browsers will still warn.
  
---
 why does proxmox need the key? how does it use the key?

● Because Proxmox is the TLS server here, and the private key is what proves it owns the certificate. Without it, the
  cert is just a public document anyone could copy.

  How it uses the key (during the TLS handshake):

  1. A browser connects to the Proxmox web UI.
  2. Proxmox sends its certificate chain (public — leaf + intermediate).
  3. The browser verifies the chain leads to your trusted root, then needs proof Proxmox actually is the holder of that
  cert — not an impostor replaying a copied cert.
  4. Proxmox proves it by performing a private-key operation the browser can verify against the public key in the cert:
    - it signs the handshake transcript with the private key (modern TLS 1.3 / ECDHE), and/or
    - it uses the key to establish the shared session secret.
  5. The math only works if Proxmox holds the private key matching the cert's public key. That's the proof of ownership.

  So the split is: cert = public identity anyone can see; key = the secret that proves the identity is yours. Proxmox
  uses the key on every connection to authenticate itself and to set up the encrypted session. That's also why the key
  must stay on the Proxmox box and never be shared — anyone with it could impersonate your server.

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
   chmod 400 pki/root/private/root-ca.key
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

4. **`variable has no value` (from OpenSSL)**
   - `openssl.conf` resolves the CA key/cert paths via `$ENV::ROOT_CA_KEY`,
     `$ENV::ROOT_CA_CERT`, `$ENV::INTERMEDIATE_CA_KEY`, and
     `$ENV::INTERMEDIATE_CA_CERT`. `pki-manager.sh` exports these automatically.
   - This error only appears when running `openssl` **directly** against the
     config; export the four variables first (see
     [CA File Naming and OpenSSL Environment Variables](#ca-file-naming-and-openssl-environment-variables)).
   