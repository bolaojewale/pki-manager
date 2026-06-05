"""Tests for MCP server tools."""

import pytest

from pki_mcp_server.config import PKIConfig, set_config
from pki_mcp_server.server import (
    pki_backup,
    pki_check,
    pki_init,
    pki_list_services,
    pki_new_cert,
    pki_status,
)


class TestMCPTools:
    """Tests for MCP tool functions."""

    @pytest.fixture(autouse=True)
    def setup_config(self, test_config: PKIConfig):
        """Set up test config for all tests."""
        set_config(test_config)

    def test_pki_status_not_initialized(self):
        """Test status when PKI not initialized."""
        result = pki_status()

        assert result["status"] == "success"
        assert result["initialized"] is False

    def test_pki_init(self):
        """Test PKI initialization."""
        result = pki_init()

        assert result["status"] == "success"
        assert "root_cert" in result
        assert "intermediate_cert" in result

    def test_pki_init_already_initialized(self):
        """Test init fails when already initialized."""
        pki_init()
        result = pki_init()

        assert result["status"] == "error"
        assert "already initialized" in result["message"].lower()

    def test_pki_init_force_without_confirmation(self):
        """Test force init requires confirmation."""
        pki_init()
        result = pki_init(force=True)

        assert result["status"] == "error"
        assert "confirm_destructive" in result["message"]

    def test_pki_init_force_with_confirmation(self):
        """Test force init with confirmation."""
        pki_init()
        result = pki_init(force=True, confirm_destructive=True)

        assert result["status"] == "success"

    def test_pki_status_initialized(self):
        """Test status after initialization."""
        pki_init()
        result = pki_status()

        assert result["status"] == "success"
        assert result["initialized"] is True
        assert result["root_online"] is True

    def test_pki_new_cert_not_initialized(self):
        """Test new cert fails without initialization."""
        result = pki_new_cert("nginx", "example.com")

        assert result["status"] == "error"
        assert "initialized" in result["message"].lower()

    def test_pki_new_cert(self):
        """Test certificate generation."""
        pki_init()
        result = pki_new_cert("nginx", "example.com")

        assert result["status"] == "success"
        assert result["service_name"] == "nginx"
        assert result["domain"] == "example.com"
        assert "certificate" in result
        assert "chain" in result

    def test_pki_new_cert_with_san(self):
        """Test certificate generation with SAN."""
        pki_init()
        result = pki_new_cert(
            "nginx",
            "example.com",
            alternate_names=["www.example.com", "192.168.1.1"],
        )

        assert result["status"] == "success"
        assert "www.example.com" in result["san"]
        assert "192.168.1.1" in result["san"]

    def test_pki_check_not_initialized(self):
        """Test check fails without initialization."""
        result = pki_check("nginx")

        assert result["status"] == "error"

    def test_pki_check_single_service(self):
        """Test checking single service."""
        pki_init()
        pki_new_cert("nginx", "example.com")
        result = pki_check("nginx")

        assert result["status"] == "success"
        assert result["service_name"] == "nginx"
        assert "days_remaining" in result
        assert result["cert_status"] == "valid"

    def test_pki_check_all_services(self):
        """Test checking all services."""
        pki_init()
        pki_new_cert("nginx", "nginx.example.com")
        pki_new_cert("apache", "apache.example.com")
        result = pki_check()

        assert result["status"] == "success"
        assert len(result["services"]) == 2

    def test_pki_list_services_empty(self):
        """Test listing when no services."""
        pki_init()
        result = pki_list_services()

        assert result["status"] == "success"
        assert result["services"] == []

    def test_pki_list_services(self):
        """Test listing services."""
        pki_init()
        pki_new_cert("nginx", "nginx.example.com")
        pki_new_cert("apache", "apache.example.com")
        result = pki_list_services()

        assert result["status"] == "success"
        assert len(result["services"]) == 2

    def test_pki_backup_not_initialized(self):
        """Test backup fails without initialization."""
        result = pki_backup()

        assert result["status"] == "error"

    def test_pki_backup(self):
        """Test backup creation."""
        pki_init()
        result = pki_backup()

        assert result["status"] == "success"
        assert "backup_file" in result

    def test_pki_new_cert_client(self):
        """Test client certificate generation."""
        pki_init()
        result = pki_new_cert(
            "api-client",
            "client.example.com",
            cert_type="client",
        )

        assert result["status"] == "success"
        assert result["cert_type"] == "client"
        assert "Client certificate generated" in result["message"]

    def test_pki_new_cert_server_explicit(self):
        """Test explicit server certificate generation."""
        pki_init()
        result = pki_new_cert(
            "web-server",
            "server.example.com",
            cert_type="server",
        )

        assert result["status"] == "success"
        assert result["cert_type"] == "server"
        assert "Server certificate generated" in result["message"]

    def test_pki_new_cert_invalid_type(self):
        """Test certificate generation with invalid type."""
        pki_init()
        result = pki_new_cert(
            "test-service",
            "test.example.com",
            cert_type="invalid",
        )

        assert result["status"] == "error"
        assert "Invalid cert_type" in result["message"]
