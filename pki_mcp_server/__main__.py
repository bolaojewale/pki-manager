"""Entry point for PKI MCP Server."""

import argparse
import sys
from pathlib import Path

from .config import ECCurve, PKIConfig, set_config
from .logging_config import setup_logging
from .server import create_server


def main() -> int:
    """Main entry point for the PKI MCP server."""
    parser = argparse.ArgumentParser(
        description="PKI Management MCP Server",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Transport options
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport protocol to use",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (SSE transport only)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to listen on (SSE transport only)",
    )

    # PKI configuration overrides
    parser.add_argument(
        "--root-dir",
        type=Path,
        help="PKI root directory (overrides PKI_ROOT_DIR env)",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        help="Backup directory (overrides PKI_BACKUP_DIR env)",
    )
    parser.add_argument(
        "--curve",
        choices=[c.value for c in ECCurve],
        help="EC curve for key generation (overrides PKI_CURVE env)",
    )
    parser.add_argument(
        "--organization",
        help="Organization name (overrides PKI_ORGANIZATION env)",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        help="Log file path (overrides PKI_LOG_FILE env)",
    )

    args = parser.parse_args()

    # Build config with CLI overrides
    config_overrides = {}
    if args.root_dir:
        config_overrides["root_dir"] = args.root_dir
    if args.backup_dir:
        config_overrides["backup_dir"] = args.backup_dir
    if args.curve:
        config_overrides["curve"] = ECCurve(args.curve)
    if args.organization:
        config_overrides["organization"] = args.organization
    if args.log_file:
        config_overrides["log_file"] = args.log_file

    # Create config (loads from env, then applies overrides)
    config = PKIConfig(**config_overrides)
    set_config(config)

    # Setup logging
    setup_logging(config.log_file)

    # Create server
    server = create_server(config)

    # Run with appropriate transport
    if args.transport == "stdio":
        server.run(transport="stdio")
    else:
        # SSE transport for Docker/remote deployment
        server.run(transport="sse", host=args.host, port=args.port)

    return 0


if __name__ == "__main__":
    sys.exit(main())
