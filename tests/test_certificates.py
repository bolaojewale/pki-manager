"""Tests for certificate operations."""

import ipaddress
from pathlib import Path

import pytest
from cryptography import x509

from pki_mcp_server.config import PKIConfig
from pki_mcp_server.exceptions import (
    CertificateNotFoundError,
    PKINotInitializedError,
    ServiceAlreadyExistsError,
)
from pki_mcp_server.pki import CAManager, CertificateManager


class TestCertificateManager:
    """Tests for CertificateManager class."""

    def test_parse_san_dns_only(self, cert_manager: CertificateManager):
        """Test SAN parsing with DNS names only."""
        san_list = cert_manager.parse_san("example.com", ["www.example.com", "api.example.com"])

        assert len(san_list) == 3
        assert all(isinstance(name, x509.DNSName) for name in san_list)

    def test_parse_san_with_ip(self, cert_manager: CertificateManager):
        """Test SAN parsing with IP addresses."""
        san_list = cert_manager.parse_san("example.com", ["192.168.1.1", "10.0.0.1"])

        dns_names = [n for n in san_list if isinstance(n, x509.DNSName)]
        ip_addresses = [n for n in san_list if isinstance(n, x509.IPAddress)]

        assert len(dns_names) == 1
        assert len(ip_addresses) == 2

    def test_parse_san_mixed(self, cert_manager: CertificateManager):
        """Test SAN parsing with mixed DNS and IP."""
        san_list = cert_manager.parse_san(
            "example.com",
            ["www.example.com", "192.168.1.1", "api.example.com", "10.0.0.1"],
        )

        dns_names = [n for n in san_list if isinstance(n, x509.DNSName)]
        ip_addresses = [n for n in san_list if isinstance(n, x509.IPAddress)]

        assert len(dns_names) == 3
        assert len(ip_addresses) == 2

    def test_validate_service_name_valid(self, cert_manager: CertificateManager):
        """Test valid service name validation."""
        assert cert_manager.validate_service_name("nginx")
        assert cert_manager.validate_service_name("my-service")
        assert cert_manager.validate_service_name("service_1")
        assert cert_manager.validate_service_name("MyService123")

    def test_validate_service_name_invalid(self, cert_manager: CertificateManager):
        """Test invalid service name validation."""
        with pytest.raises(ValueError):
            cert_manager.validate_service_name("")

        with pytest.raises(ValueError):
            cert_manager.validate_service_name("-invalid")

        with pytest.raises(ValueError):
            cert_manager.validate_service_name("_invalid")

        with pytest.raises(ValueError):
            cert_manager.validate_service_name("has spaces")

    def test_generate_certificate_not_initialized(self, cert_manager: CertificateManager):
        """Test certificate generation fails without PKI initialization."""
        with pytest.raises(PKINotInitializedError):
            cert_manager.generate_certificate("nginx", "example.com")

    def test_generate_certificate(
        self,
        cert_manager: CertificateManager,
        initialized_pki: dict,
        test_config: PKIConfig,
    ):
        """Test certificate generation."""
        result = cert_manager.generate_certificate("nginx", "example.com")

        assert result["service_name"] == "nginx"
        assert result["domain"] == "example.com"
        assert "certificate" in result
        assert "private_key" in result

        # Check files exist
        cert_path = test_config.service_cert_path("nginx")
        key_path = test_config.service_key_path("nginx")

        assert cert_path.exists()
        assert key_path.exists()

    def test_generate_certificate_with_san(
        self,
        cert_manager: CertificateManager,
        ca_manager: CAManager,
        initialized_pki: dict,
        test_config: PKIConfig,
    ):
        """Test certificate generation with SAN."""
        result = cert_manager.generate_certificate(
            "nginx",
            "example.com",
            alternate_names=["www.example.com", "192.168.1.1"],
        )

        assert "san" in result
        assert "example.com" in result["san"]
        assert "www.example.com" in result["san"]
        assert "192.168.1.1" in result["san"]

        # Load and verify certificate
        cert = ca_manager.load_certificate(test_config.service_cert_path("nginx"))
        san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        san_values = [str(name.value) for name in san_ext.value]

        assert "example.com" in san_values
        assert "www.example.com" in san_values

    def test_generate_certificate_already_exists(
        self,
        cert_manager: CertificateManager,
        initialized_pki: dict,
    ):
        """Test certificate generation fails if service exists."""
        cert_manager.generate_certificate("nginx", "example.com")

        with pytest.raises(ServiceAlreadyExistsError):
            cert_manager.generate_certificate("nginx", "example.com")

    def test_generate_certificate_overwrite(
        self,
        cert_manager: CertificateManager,
        initialized_pki: dict,
    ):
        """Test certificate overwrite."""
        cert_manager.generate_certificate("nginx", "example.com")
        result = cert_manager.generate_certificate("nginx", "new.example.com", overwrite=True)

        assert result["domain"] == "new.example.com"

    def test_check_expiration_single(
        self,
        cert_manager: CertificateManager,
        initialized_pki: dict,
    ):
        """Test single service expiration check."""
        cert_manager.generate_certificate("nginx", "example.com")

        result = cert_manager.check_expiration("nginx")

        assert result["service_name"] == "nginx"
        assert "days_remaining" in result
        assert result["cert_status"] == "valid"

    def test_check_expiration_not_found(
        self,
        cert_manager: CertificateManager,
        initialized_pki: dict,
    ):
        """Test expiration check for non-existent service."""
        with pytest.raises(CertificateNotFoundError):
            cert_manager.check_expiration("nonexistent")

    def test_check_expiration_all(
        self,
        cert_manager: CertificateManager,
        initialized_pki: dict,
    ):
        """Test all services expiration check."""
        cert_manager.generate_certificate("nginx", "nginx.example.com")
        cert_manager.generate_certificate("apache", "apache.example.com")

        result = cert_manager.check_expiration()

        assert "services" in result
        assert "summary" in result
        assert result["summary"]["total"] == 2

    def test_list_services_empty(
        self,
        cert_manager: CertificateManager,
        initialized_pki: dict,
    ):
        """Test listing services when none exist."""
        result = cert_manager.list_services()

        assert result["services"] == []

    def test_list_services(
        self,
        cert_manager: CertificateManager,
        initialized_pki: dict,
    ):
        """Test listing services."""
        cert_manager.generate_certificate("nginx", "nginx.example.com")
        cert_manager.generate_certificate("apache", "apache.example.com")

        result = cert_manager.list_services()

        assert len(result["services"]) == 2
        service_names = [s["name"] for s in result["services"]]
        assert "nginx" in service_names
        assert "apache" in service_names

    def test_generate_client_certificate(
        self,
        cert_manager: CertificateManager,
        ca_manager: CAManager,
        initialized_pki: dict,
        test_config: PKIConfig,
    ):
        """Test client certificate generation."""
        result = cert_manager.generate_certificate(
            "api-client",
            "client.example.com",
            cert_type="client",
        )

        assert result["service_name"] == "api-client"
        assert result["cert_type"] == "client"

        # Load and verify certificate extensions
        cert = ca_manager.load_certificate(test_config.service_cert_path("api-client"))

        # Check ExtendedKeyUsage is clientAuth
        eku_ext = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage)
        assert x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH in eku_ext.value

        # Check KeyUsage - should NOT have keyEncipherment
        ku_ext = cert.extensions.get_extension_for_class(x509.KeyUsage)
        assert ku_ext.value.digital_signature is True
        assert ku_ext.value.key_encipherment is False

    def test_generate_server_certificate_explicit(
        self,
        cert_manager: CertificateManager,
        ca_manager: CAManager,
        initialized_pki: dict,
        test_config: PKIConfig,
    ):
        """Test explicit server certificate generation."""
        result = cert_manager.generate_certificate(
            "web-server",
            "server.example.com",
            cert_type="server",
        )

        assert result["cert_type"] == "server"

        # Load and verify certificate extensions
        cert = ca_manager.load_certificate(test_config.service_cert_path("web-server"))

        # Check ExtendedKeyUsage is serverAuth
        eku_ext = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage)
        assert x509.oid.ExtendedKeyUsageOID.SERVER_AUTH in eku_ext.value

        # Check KeyUsage - should have keyEncipherment
        ku_ext = cert.extensions.get_extension_for_class(x509.KeyUsage)
        assert ku_ext.value.digital_signature is True
        assert ku_ext.value.key_encipherment is True

    def test_generate_certificate_invalid_cert_type(
        self,
        cert_manager: CertificateManager,
        initialized_pki: dict,
    ):
        """Test certificate generation with invalid cert_type."""
        with pytest.raises(ValueError, match="Invalid cert_type"):
            cert_manager.generate_certificate(
                "test-service",
                "test.example.com",
                cert_type="invalid",
            )
