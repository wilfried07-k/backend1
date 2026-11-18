import os

import oracledb
from dotenv import load_dotenv
from sqlmodel import Session, create_engine

load_dotenv()

# Preview defaults to a local SQLite database. Production deployments should
# provide DATABASE_URL for a managed PostgreSQL or Oracle database.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./emploicamer.db")

# Oracle XE 11 requires Oracle Instant Client (thick mode). Newer Oracle
# connections can use python-oracledb thin mode without a local client.
ORACLE_CLIENT_LIB_DIR = os.getenv("ORACLE_CLIENT_LIB_DIR")
if not ORACLE_CLIENT_LIB_DIR:
    legacy_oracle_path = r"C:\oraclexe\app\oracle\product\11.2.0\server\bin"
    if os.path.isdir(legacy_oracle_path):
        ORACLE_CLIENT_LIB_DIR = legacy_oracle_path
if DATABASE_URL.startswith("oracle+") and ORACLE_CLIENT_LIB_DIR:
    oracledb.init_oracle_client(lib_dir=ORACLE_CLIENT_LIB_DIR)

# Hosting providers may supply postgres:// or postgresql:// URLs. The project
# installs psycopg 3, so make that driver explicit for SQLAlchemy.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgres://"):]
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://"):]

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    connect_args=connect_args,
)

"""def get_setup_engine():
    return engine"""

def get_session():
    """Provide a SQLModel session for a request and close it afterward."""
    with Session(engine) as session:
        yield session

