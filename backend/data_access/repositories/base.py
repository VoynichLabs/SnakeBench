"""
Base repository with connection management.

Provides a context manager for database connections that handles:
- Automatic connection cleanup
- Transaction commit on success
- Transaction rollback on failure
"""

from contextlib import contextmanager
from typing import Generator, Any
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database_postgres import get_connection


class BaseRepository:
    """
    Base class for all repositories.

    Provides connection management via context manager pattern.
    Subclasses should use self.connection() to get database connections.
    """

    @contextmanager
    def connection(self, auto_commit: bool = True) -> Generator[Any, None, None]:
        """
        Context manager for database connections.

        Automatically handles:
        - Getting a connection from the pool
        - Committing on successful exit (if auto_commit=True)
        - Rolling back on exception
        - Closing the connection in all cases

        Args:
            auto_commit: If True, commit transaction on successful exit.
                        Set to False if you want to manage transactions manually.

        Yields:
            A tuple of (connection, cursor) for database operations.

        Example:
            with self.connection() as (conn, cursor):
                cursor.execute("SELECT * FROM models")
                results = cursor.fetchall()
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            yield conn, cursor
            if auto_commit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    @contextmanager
    def read_connection(self) -> Generator[Any, None, None]:
        """
        Context manager for read-only operations.

        Same as connection() but with auto_commit=False since
        read operations don't need commits.

        Yields:
            A tuple of (connection, cursor) for database operations.
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            yield conn, cursor
        except Exception:
            raise
        finally:
            cursor.close()
            conn.close()
