"""Pytest fixtures for PKI MCP Server tests."""

import shutil
from pathlib import Path

import pytest

from pki_mcp_server.config import PKIConfig, set_config
from pki_mcp_server.pki import BackupManager, CAManager, CertificateManager, ChainManager


@pytest.fixture
def temp_pki_dir(tmp_path: Path) -> Path:
    """Create a temporary PKI directory."""
    pki_dir = tmp_path / "pki"
    pki_dir.mkdir()
    return pki_dir


@pytest.fixture
def temp_backup_dir(tmp_path: Path) -> Path:
    """Create a temporary backup directory."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    return backup_dir


@pytest.fixture
def test_config(temp_pki_dir: Path, temp_backup_dir: Path) -> PKIConfig:
    """Create a test configuration."""
    config = PKIConfig(
        root_dir=temp_pki_dir,
        backup_dir=temp_backup_dir,
        organization="Test Org",
        country="US",
        state="Test State",
        locality="Test City",
        root_cn="Test Root CA",
        intermediate_cn="Test Intermediate CA",
        root_validity=365,
        intermediate_validity=180,
        leaf_validity=90,
        log_file=None,  # Disable file logging in tests
    )
    set_config(config)
    return config


@pytest.fixture
def ca_manager(test_config: PKIConfig) -> CAManager:
    """Create a CA manager instance."""
    return CAManager(test_config)


@pytest.fixture
def cert_manager(test_config: PKIConfig, ca_manager: CAManager) -> CertificateManager:
    """Create a certificate manager instance."""
    return CertificateManager(test_config, ca_manager)


@pytest.fixture
def chain_manager(test_config: PKIConfig, ca_manager: CAManager) -> ChainManager:
    """Create a chain manager instance."""
    return ChainManager(test_config, ca_manager)


@pytest.fixture
def backup_manager(test_config: PKIConfig, ca_manager: CAManager) -> BackupManager:
    """Create a backup manager instance."""
    return BackupManager(test_config, ca_manager)


@pytest.fixture
def initialized_pki(ca_manager: CAManager, chain_manager: ChainManager) -> dict:
    """Initialize PKI and return the result."""
    result = ca_manager.initialize_pki()
    chain_manager.create_ca_chains()
    return result
