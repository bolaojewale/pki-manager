"""Configuration module using Pydantic settings."""

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ECCurve(str, Enum):
    """Supported elliptic curves for key generation."""

    PRIME256V1 = "prime256v1"
    SECP384R1 = "secp384r1"
    SECP521R1 = "secp521r1"


class PKIConfig(BaseSettings):
    """PKI configuration loaded from environment variables or config file."""

    model_config = SettingsConfigDict(
        env_prefix="PKI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Cryptographic settings
    curve: ECCurve = Field(
        default=ECCurve.PRIME256V1,
        description="Elliptic curve for key generation",
    )

    # Certificate validity periods (in days)
    root_validity: int = Field(
        default=1460,  # 4 years
        ge=365,
        le=7300,
        description="Root CA validity in days",
    )
    intermediate_validity: int = Field(
        default=730,  # 2 years
        ge=180,
        le=3650,
        description="Intermediate CA validity in days",
    )
    leaf_validity: int = Field(
        default=180,  # 6 months
        ge=30,
        le=825,  # Max allowed by browsers
        description="Leaf certificate validity in days",
    )

    # Directory structure
    root_dir: Path = Field(
        default=Path("pki"),
        description="Root directory for PKI files",
    )
    backup_dir: Path = Field(
        default=Path("backups"),
        description="Directory for backups",
    )

    # Certificate subject defaults
    country: str = Field(
        default="US",
        min_length=2,
        max_length=2,
        description="Two-letter country code",
    )
    state: str = Field(
        default="State",
        min_length=1,
        max_length=128,
        description="State or province",
    )
    locality: str = Field(
        default="City",
        min_length=1,
        max_length=128,
        description="City or locality",
    )
    organization: str = Field(
        default="Home",
        min_length=1,
        max_length=64,
        description="Organization name",
    )
    root_cn: str = Field(
        default="Root CA",
        min_length=1,
        max_length=64,
        description="Root CA common name",
    )
    intermediate_cn: str = Field(
        default="Intermediate CA",
        min_length=1,
        max_length=64,
        description="Intermediate CA common name",
    )

    # Backup settings
    backup_enabled: bool = Field(
        default=True,
        description="Enable automatic backups",
    )

    # Logging
    log_file: Optional[Path] = Field(
        default=Path("pki-manager.log"),
        description="Log file path (None for stdout only)",
    )

    @field_validator("country")
    @classmethod
    def validate_country(cls, v: str) -> str:
        """Validate country is uppercase two-letter code."""
        return v.upper()

    @property
    def root_key_path(self) -> Path:
        """Path to root CA private key."""
        return self.root_dir / "root" / "private" / "ca.key"

    @property
    def root_cert_path(self) -> Path:
        """Path to root CA certificate."""
        return self.root_dir / "root" / "certs" / "ca.crt"

    @property
    def intermediate_key_path(self) -> Path:
        """Path to intermediate CA private key."""
        return self.root_dir / "intermediate" / "private" / "intermediate.key"

    @property
    def intermediate_cert_path(self) -> Path:
        """Path to intermediate CA certificate."""
        return self.root_dir / "intermediate" / "certs" / "intermediate.crt"

    @property
    def intermediate_csr_path(self) -> Path:
        """Path to intermediate CA CSR."""
        return self.root_dir / "intermediate" / "csr" / "intermediate.csr"

    @property
    def chains_dir(self) -> Path:
        """Path to certificate chains directory."""
        return self.root_dir / "chains"

    @property
    def services_dir(self) -> Path:
        """Path to services directory."""
        return self.root_dir / "services"

    @property
    def org_filename(self) -> str:
        """Organization name formatted for filenames (lowercase, hyphenated)."""
        return self.organization.lower().replace(" ", "-")

    def service_dir(self, service_name: str) -> Path:
        """Get path to a service's directory."""
        return self.services_dir / service_name

    def service_key_path(self, service_name: str) -> Path:
        """Get path to a service's private key."""
        return self.service_dir(service_name) / "private" / f"{service_name}.key"

    def service_cert_path(self, service_name: str) -> Path:
        """Get path to a service's certificate."""
        return self.service_dir(service_name) / "certs" / f"{service_name}.crt"

    def service_csr_path(self, service_name: str) -> Path:
        """Get path to a service's CSR."""
        return self.service_dir(service_name) / "csr" / f"{service_name}.csr"

    def service_chain_path(self, service_name: str) -> Path:
        """Get path to a service's certificate chain."""
        return self.service_dir(service_name) / "chains" / f"{service_name}-chain.crt"


# Global config instance - will be initialized on server startup
_config: Optional[PKIConfig] = None


def get_config() -> PKIConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = PKIConfig()
    return _config


def set_config(config: PKIConfig) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config
