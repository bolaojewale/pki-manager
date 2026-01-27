"""Tests for CA operations."""

from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import ec

from pki_mcp_server.config import PKIConfig
from pki_mcp_server.exceptions import PKIAlreadyInitializedError, RootCAOfflineError
from pki_mcp_server.pki import CAManager


class TestCAManager:
    """Tests for CAManager class."""

    def test_generate_ec_private_key(self, ca_manager: CAManager):
        """Test EC key generation."""
        key = ca_manager.generate_ec_private_key()
        assert isinstance(key, ec.EllipticCurvePrivateKey)

    def test_create_root_ca(self, ca_manager: CAManager):
        """Test root CA creation."""
        key, cert = ca_manager.create_root_ca()

        assert isinstance(key, ec.EllipticCurvePrivateKey)
        assert isinstance(cert, x509.Certificate)

        # Check certificate properties
        assert cert.subject == cert.issuer  # Self-signed
        basic_constraints = cert.extensions.get_extension_for_class(x509.BasicConstraints)
        assert basic_constraints.value.ca is True

    def test_create_intermediate_ca(self, ca_manager: CAManager):
        """Test intermediate CA creation."""
        root_key, root_cert = ca_manager.create_root_ca()
        int_key, int_cert, csr = ca_manager.create_intermediate_ca(root_key, root_cert)

        assert isinstance(int_key, ec.EllipticCurvePrivateKey)
        assert isinstance(int_cert, x509.Certificate)
        assert isinstance(csr, x509.CertificateSigningRequest)

        # Check intermediate is signed by root
        assert int_cert.issuer == root_cert.subject

        # Check it's a CA
        basic_constraints = int_cert.extensions.get_extension_for_class(x509.BasicConstraints)
        assert basic_constraints.value.ca is True
        assert basic_constraints.value.path_length == 0

    def test_save_and_load_private_key(self, ca_manager: CAManager, tmp_path: Path):
        """Test saving and loading private keys."""
        key = ca_manager.generate_ec_private_key()
        key_path = tmp_path / "test.key"

        ca_manager.save_private_key(key, key_path)

        assert key_path.exists()
        # Check permissions (0o400)
        assert (key_path.stat().st_mode & 0o777) == 0o400

        loaded_key = ca_manager.load_private_key(key_path)
        assert isinstance(loaded_key, ec.EllipticCurvePrivateKey)

    def test_save_and_load_certificate(self, ca_manager: CAManager, tmp_path: Path):
        """Test saving and loading certificates."""
        _, cert = ca_manager.create_root_ca()
        cert_path = tmp_path / "test.crt"

        ca_manager.save_certificate(cert, cert_path)

        assert cert_path.exists()

        loaded_cert = ca_manager.load_certificate(cert_path)
        assert loaded_cert.serial_number == cert.serial_number

    def test_create_directory_structure(self, ca_manager: CAManager, test_config: PKIConfig):
        """Test PKI directory structure creation."""
        ca_manager.create_directory_structure()

        # Check directories exist
        assert (test_config.root_dir / "root" / "private").exists()
        assert (test_config.root_dir / "root" / "certs").exists()
        assert (test_config.root_dir / "intermediate" / "private").exists()
        assert (test_config.root_dir / "intermediate" / "certs").exists()
        assert test_config.chains_dir.exists()

        # Check private directories have restricted permissions
        root_private = test_config.root_dir / "root" / "private"
        assert (root_private.stat().st_mode & 0o777) == 0o700

    def test_initialize_pki(self, ca_manager: CAManager, test_config: PKIConfig):
        """Test full PKI initialization."""
        result = ca_manager.initialize_pki()

        assert "root_cert" in result
        assert "root_key" in result
        assert "intermediate_cert" in result
        assert "intermediate_key" in result

        # Check files exist
        assert test_config.root_cert_path.exists()
        assert test_config.root_key_path.exists()
        assert test_config.intermediate_cert_path.exists()
        assert test_config.intermediate_key_path.exists()

    def test_initialize_pki_already_exists(self, ca_manager: CAManager):
        """Test initialization fails if PKI already exists."""
        ca_manager.initialize_pki()

        with pytest.raises(PKIAlreadyInitializedError):
            ca_manager.initialize_pki()

    def test_initialize_pki_force(self, ca_manager: CAManager):
        """Test forced reinitialization."""
        ca_manager.initialize_pki()
        result = ca_manager.initialize_pki(force=True)

        assert "root_cert" in result

    def test_is_initialized(self, ca_manager: CAManager):
        """Test initialization status check."""
        assert not ca_manager.is_initialized()

        ca_manager.initialize_pki()

        assert ca_manager.is_initialized()

    def test_is_root_online(self, ca_manager: CAManager):
        """Test root CA online status."""
        ca_manager.initialize_pki()

        assert ca_manager.is_root_online()

    def test_get_status(self, ca_manager: CAManager):
        """Test PKI status retrieval."""
        # Before initialization
        status = ca_manager.get_status()
        assert status["initialized"] is False

        # After initialization
        ca_manager.initialize_pki()
        status = ca_manager.get_status()

        assert status["initialized"] is True
        assert status["root_online"] is True
        assert "intermediate_ca" in status
        assert "root_ca" in status

    def test_secure_delete(self, ca_manager: CAManager, tmp_path: Path):
        """Test secure file deletion."""
        test_file = tmp_path / "secret.key"
        test_file.write_bytes(b"secret data")

        ca_manager.secure_delete(test_file)

        assert not test_file.exists()

    def test_offline_root_ca(self, ca_manager: CAManager, tmp_path: Path):
        """Test taking root CA offline."""
        ca_manager.initialize_pki()
        backup_path = tmp_path / "offline_backup"
        backup_path.mkdir()

        result = ca_manager.offline_root_ca(backup_path)

        assert result["root_key_deleted"] is True
        assert not ca_manager.is_root_online()

        # Check backup was created
        assert len(result["files"]) > 0

    def test_offline_root_ca_already_offline(self, ca_manager: CAManager, tmp_path: Path):
        """Test error when root CA already offline."""
        ca_manager.initialize_pki()
        backup_path = tmp_path / "offline_backup"
        backup_path.mkdir()

        ca_manager.offline_root_ca(backup_path)

        with pytest.raises(RootCAOfflineError):
            ca_manager.offline_root_ca(backup_path)
