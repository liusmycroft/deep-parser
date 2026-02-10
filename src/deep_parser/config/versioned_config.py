"""Versioned configuration management for Deep Parser.

This module provides database-backed versioned configuration storage and management,
allowing configuration changes to be tracked, rolled back, and activated as needed.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, Column, DateTime, String, Text, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from deep_parser.models.database import Base


class ConfigVersionModel(Base):
    """SQLAlchemy model for storing configuration versions.

    Attributes:
        config_version_id: Unique identifier for the configuration version
        config_data: Serialized configuration data (JSON)
        is_active: Whether this version is currently active
        created_at: Timestamp when this version was created
    """

    __tablename__ = "config_versions"

    config_version_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    config_data = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


@dataclass
class ConfigVersion:
    """Data class representing a configuration version.

    Attributes:
        config_version_id: Unique identifier for the configuration version
        config_data: Dictionary containing the configuration data
        is_active: Whether this version is currently active
        created_at: Timestamp when this version was created
    """

    config_version_id: str
    config_data: Dict[str, Any]
    is_active: bool
    created_at: datetime = field(default_factory=datetime.utcnow)


class ConfigVersionManager:
    """Manager for versioned configuration operations.

    Provides methods to save, retrieve, activate, and list configuration versions
    stored in the database. All operations are async and require an AsyncSession.

    Attributes:
        session: Async database session for database operations
    """

    def __init__(self, session: AsyncSession):
        """Initialize the configuration version manager.

        Args:
            session: Async database session for database operations
        """
        self.session = session

    async def save_config(self, config_data: Dict[str, Any]) -> str:
        """Save a new configuration version to the database.

        The configuration is saved as inactive by default. Use activate_config()
        to make it the active configuration.

        Args:
            config_data: Dictionary containing the configuration to save

        Returns:
            The version ID of the newly saved configuration

        Raises:
            sqlalchemy.exc.SQLAlchemyError: If database operation fails
        """
        import json

        config_version_id = str(uuid.uuid4())
        serialized_data = json.dumps(config_data, ensure_ascii=False)

        config_version = ConfigVersionModel(
            config_version_id=config_version_id,
            config_data=serialized_data,
            is_active=False,
        )

        self.session.add(config_version)
        await self.session.flush()

        return config_version_id

    async def get_active_config(self) -> Optional[Dict[str, Any]]:
        """Retrieve the currently active configuration.

        Returns:
            Dictionary containing the active configuration data, or None if no
            active configuration exists

        Raises:
            sqlalchemy.exc.SQLAlchemyError: If database operation fails
        """
        import json

        result = await self.session.execute(
            select(ConfigVersionModel).where(ConfigVersionModel.is_active == True)
        )
        config_version = result.scalar_one_or_none()

        if config_version is None:
            return None

        return json.loads(config_version.config_data)

    async def get_config_by_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific configuration version.

        Args:
            version_id: The version ID to retrieve

        Returns:
            Dictionary containing the configuration data, or None if the version
            does not exist

        Raises:
            sqlalchemy.exc.SQLAlchemyError: If database operation fails
        """
        import json

        result = await self.session.execute(
            select(ConfigVersionModel).where(ConfigVersionModel.config_version_id == version_id)
        )
        config_version = result.scalar_one_or_none()

        if config_version is None:
            return None

        return json.loads(config_version.config_data)

    async def activate_config(self, version_id: str) -> bool:
        """Activate a specific configuration version.

        This will deactivate the currently active configuration (if any) and
        activate the specified version. Only one configuration can be active
        at a time.

        Args:
            version_id: The version ID to activate

        Returns:
            True if the configuration was activated successfully, False if the
            version does not exist

        Raises:
            sqlalchemy.exc.SQLAlchemyError: If database operation fails
        """
        result = await self.session.execute(
            select(ConfigVersionModel).where(ConfigVersionModel.config_version_id == version_id)
        )
        config_version = result.scalar_one_or_none()

        if config_version is None:
            return False

        await self.session.execute(
            update(ConfigVersionModel)
            .where(ConfigVersionModel.is_active == True)
            .values(is_active=False)
        )

        config_version.is_active = True
        await self.session.flush()

        return True

    async def list_versions(self) -> List[ConfigVersion]:
        """List all configuration versions.

        Returns:
            List of ConfigVersion objects, ordered by creation time (newest first)

        Raises:
            sqlalchemy.exc.SQLAlchemyError: If database operation fails
        """
        import json

        result = await self.session.execute(
            select(ConfigVersionModel).order_by(ConfigVersionModel.created_at.desc())
        )
        config_versions = result.scalars().all()

        return [
            ConfigVersion(
                config_version_id=cv.config_version_id,
                config_data=json.loads(cv.config_data),
                is_active=cv.is_active,
                created_at=cv.created_at,
            )
            for cv in config_versions
        ]
