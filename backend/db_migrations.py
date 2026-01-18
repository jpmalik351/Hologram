"""
Database Migrations - Initialize database schema

Simple migration script to create tables if they don't exist.
For production, consider using Flask-Migrate/Alembic for proper migrations.
"""

from database import db, init_db
from flask import Flask
import os


def initialize_database():
    """
    Initialize database and create all tables.
    
    This function can be called on app startup to ensure database is ready.
    """
    app = Flask(__name__)
    init_db(app)
    
    with app.app_context():
        db.create_all()
        print("Database initialized successfully")


if __name__ == "__main__":
    initialize_database()
