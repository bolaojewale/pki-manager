"""FastMCP server with PKI management tools."""

from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from .config import PKIConfig, get_config, set_config
from .exceptions import ConfirmationRequiredError, PKIError
from .logging_config import get_logger, setup_logging
from .pki import BackupManager, CAManager, CertificateManager, ChainManager

logger = get_logger("server")

# Create MCP server instance
mcp = FastMCP(
    "PKI Manager",
    instructions="PKI management server for creating and managing TLS certificates using elliptic curve cryptography",
)


def get_managers() -> tuple[CAManager, CertificateManager, ChainManager, BackupManager]:
    """Get initialized manager instances."""
    config = get_config()
    ca_manager = CAManager(config)
    cert_manager = CertificateManager(config, ca_manager)
    chain_manager = ChainManager(config, ca_manager)
    backup_manager = BackupManager(config, ca_manager)
    return ca_manager, cert_manager, chain_manager, backup_manager


def handle_error(e: Exception) -> dict:
    """Convert exception to error response."""
    if isinstance(e, PKIError):
        return {"status": "error", **e.to_dict()}
    return {"status": "error", "error": type(e).__name__, "message": str(e)}


@mcp.tool()
def pki_init(
    confirm_destructive: Annotated[
        bool,
        Field(description="Must be true to confirm destructive operation if PKI exists"),
    ] = False,
    force: Annotated[
        bool,
        Field(description="If true, reinitialize even if PKI already exists"),
    ] = False,
) -> dict:
    """Initialize PKI structure with Root CA and Intermediate CA.

    Creates the complete PKI directory structure, generates a self-signed Root CA,
    and an Intermediate CA signed by the Root. The Intermediate CA is used for
    day-to-day certificate signing operations.

    This is a destructive operation if PKI already exists - requires confirm_destructive=true.

    Args:
        confirm_destructive: Must be true if PKI exists and force is true.
        force: If true, reinitialize even if PKI exists.

    Returns:
        Dictionary with paths to created CA certificates and keys.
    """
    try:
        ca_manager, _, chain_manager, backup_manager = get_managers()

        # Check if destructive confirmation is needed
        if ca_manager.is_initialized() and force and not confirm_destructive:
            raise ConfirmationRequiredError("pki_init with force=true")

        # Initialize PKI
        result = ca_manager.initialize_pki(force=force)

        # Create certificate chains
        chains = chain_manager.create_ca_chains()
        result["chains"] = chains

        # Create backup if enabled
        backup_result = backup_manager.create_backup()
        if backup_result.get("status") == "success":
            result["backup"] = backup_result["backup_file"]

        return {
            "status": "success",
            "message": "PKI initialized successfully",
            **result,
        }

    except Exception as e:
        logger.exception("Failed to initialize PKI")
        return handle_error(e)


@mcp.tool()
def pki_new_cert(
    service_name: Annotated[
        str,
        Field(description="Name of the service (e.g., nginx, apache, myapp)"),
    ],
    domain: Annotated[
        str,
        Field(description="Primary domain name for the certificate"),
    ],
    alternate_names: Annotated[
        list[str] | None,
        Field(description="Additional DNS names or IP addresses for SAN extension"),
    ] = None,
    csr_path: Annotated[
        str | None,
        Field(description="Optional path to existing CSR file to sign"),
    ] = None,
    overwrite: Annotated[
        bool,
        Field(description="If true, overwrite existing service certificate"),
    ] = False,
) -> dict:
    """Generate a new leaf certificate for a service.

    Creates a new EC private key (if no CSR provided), generates a certificate
    signed by the Intermediate CA, and creates the certificate chain file.

    Args:
        service_name: Identifier for the service.
        domain: Primary domain for the certificate's CN and SAN.
        alternate_names: Additional DNS names or IP addresses.
        csr_path: Path to existing CSR (optional - key won't be generated).
        overwrite: Replace existing certificate for this service.

    Returns:
        Dictionary with paths to certificate, key, and chain files.
    """
    try:
        ca_manager, cert_manager, chain_manager, _ = get_managers()

        # Generate certificate
        csr = Path(csr_path) if csr_path else None
        result = cert_manager.generate_certificate(
            service_name=service_name,
            domain=domain,
            alternate_names=alternate_names,
            csr_path=csr,
            overwrite=overwrite,
        )

        # Create service chain
        chain_result = chain_manager.create_service_chain(service_name)
        result["chain"] = chain_result["chain_file"]

        return {
            "status": "success",
            "message": f"Certificate generated for {service_name}",
            **result,
        }

    except Exception as e:
        logger.exception(f"Failed to generate certificate for {service_name}")
        return handle_error(e)


@mcp.tool()
def pki_check(
    service_name: Annotated[
        str | None,
        Field(description="Service name to check, or omit to check all services"),
    ] = None,
) -> dict:
    """Check certificate expiration for services.

    Returns expiration information including days remaining and status
    (valid, expiring_soon, expired).

    Args:
        service_name: Check specific service, or all if not provided.

    Returns:
        Dictionary with expiration information.
    """
    try:
        _, cert_manager, _, _ = get_managers()

        result = cert_manager.check_expiration(service_name)
        return {
            "status": "success",
            **result,
        }

    except Exception as e:
        logger.exception("Failed to check certificate expiration")
        return handle_error(e)


@mcp.tool()
def pki_backup(
    include_private_keys: Annotated[
        bool,
        Field(description="Include private keys in backup (security risk!)"),
    ] = False,
) -> dict:
    """Create a backup of the PKI directory.

    By default excludes private keys for security. The backup is a tar.gz
    archive containing certificates, chains, and CSRs.

    Args:
        include_private_keys: If true, include private keys (not recommended).

    Returns:
        Dictionary with backup file path and details.
    """
    try:
        _, _, _, backup_manager = get_managers()

        result = backup_manager.create_backup(include_private_keys=include_private_keys)
        return result

    except Exception as e:
        logger.exception("Failed to create backup")
        return handle_error(e)


@mcp.tool()
def pki_offline_root(
    backup_path: Annotated[
        str,
        Field(description="Directory path to store the root CA backup"),
    ],
    confirm_destructive: Annotated[
        bool,
        Field(description="Must be true to confirm this destructive operation"),
    ] = False,
) -> dict:
    """Take root CA private key offline for secure storage.

    Creates a backup of the root CA key and certificate, then securely
    deletes the root CA private key from disk. After this operation,
    you cannot create new intermediate CAs without restoring the backup.

    This is a DESTRUCTIVE operation - the root key is securely deleted!

    Args:
        backup_path: Directory to store the root CA backup.
        confirm_destructive: Must be true to proceed.

    Returns:
        Dictionary with backup location and confirmation.
    """
    try:
        if not confirm_destructive:
            raise ConfirmationRequiredError("pki_offline_root")

        ca_manager, _, _, _ = get_managers()

        result = ca_manager.offline_root_ca(Path(backup_path))
        return {
            "status": "success",
            "message": "Root CA taken offline successfully",
            "important": [
                "Copy backup to encrypted USB drive",
                "Store in secure physical location",
                "Create multiple backup copies",
                "Verify backup before deleting from this location",
            ],
            **result,
        }

    except Exception as e:
        logger.exception("Failed to take root CA offline")
        return handle_error(e)


@mcp.tool()
def pki_status() -> dict:
    """Get current PKI status.

    Returns information about whether PKI is initialized, if root CA
    is online or offline, and certificate details.

    Returns:
        Dictionary with PKI status information.
    """
    try:
        ca_manager, _, _, _ = get_managers()

        result = ca_manager.get_status()
        return {
            "status": "success",
            **result,
        }

    except Exception as e:
        logger.exception("Failed to get PKI status")
        return handle_error(e)


@mcp.tool()
def pki_list_services() -> dict:
    """List all services with certificates.

    Returns a list of all services that have certificates, including
    their domain names and expiration dates.

    Returns:
        Dictionary with list of services and their details.
    """
    try:
        _, cert_manager, _, _ = get_managers()

        result = cert_manager.list_services()
        return {
            "status": "success",
            **result,
        }

    except Exception as e:
        logger.exception("Failed to list services")
        return handle_error(e)


def create_server(config: PKIConfig | None = None) -> FastMCP:
    """Create and configure the MCP server.

    Args:
        config: Optional PKI configuration. If not provided, loads from environment.

    Returns:
        Configured FastMCP server instance.
    """
    if config:
        set_config(config)
    else:
        # Initialize with defaults (loads from environment)
        set_config(PKIConfig())

    cfg = get_config()

    # Setup logging
    setup_logging(cfg.log_file)

    logger.info(f"PKI MCP Server initialized with root_dir={cfg.root_dir}")

    return mcp
