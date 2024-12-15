"""Manage Config table in database."""

from datetime import datetime
import logging
import sqlite3

from contextlib import contextmanager
from sqlalchemy import select

from db_schema import Ecowatt

from . import DB


class DatabaseEcowatt:
    """Manage configuration for the database."""

    def __init__(self):
        pass  # No session initialization here

    @contextmanager
    def _session_scope(self):
        """Provide a transactional scope around a series of operations."""
        session = DB.session()
        try:
            yield session
            if session.dirty:  # Check if there are changes to commit
                session.commit()
        except Exception as e:
            session.rollback()
            logging.error(f"Transaction failed: {e}")  # Log the error for debugging
            raise
        finally:
            session.close()

    def get(self, order="desc"):
        """Retrieve Ecowatt data from the database."""
        try:
            with self._session_scope() as session:
                if order == "desc":
                    order = Ecowatt.date.desc()
                else:
                    order = Ecowatt.date.asc()
                return session.scalars(select(Ecowatt).order_by(order)).all()
        except Exception as e:
            logging.error(f"Error retrieving Ecowatt data: {e}")
            raise

    def get_range(self, begin, end, order="desc"):
        """Retrieve a range of Ecowatt data from the database."""
        attempts = 3
        for attempt in range(attempts):
            try:
                with self._session_scope() as session:
                    if order == "desc":
                        order = Ecowatt.date.desc()
                    else:
                        order = Ecowatt.date.asc()
                    return session.scalars(
                        select(Ecowatt).where(Ecowatt.date >= begin).where(Ecowatt.date <= end).order_by(order)
                    ).all()
            except sqlite3.OperationalError as e:
                if attempt < attempts - 1:
                    logging.warning(f"Database is locked, retrying... (attempt {attempt + 1})")
                else:
                    logging.error(f"Failed to retrieve Ecowatt data after {attempts} attempts: {e}")
                    raise e

    def set(self, date, value, message, detail):
        date = datetime.combine(date, datetime.min.time())
        with self._session_scope() as session:
        # Check if a record already exists for the given date
            ecowatt = session.scalars(
                select(Ecowatt).where(Ecowatt.date == date)
            ).all()
        
        if ecowatt:
            # Update existing records
            for item in ecowatt:
                item.value = value
                item.message = message
                item.detail = detail
        else:
            # Create a new record if none exists
            ecowatt_record = Ecowatt(date=date, value=value, message=message, detail=detail)
            session.add(ecowatt_record)  # Add the new record to the session