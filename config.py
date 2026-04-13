import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

# ============================================================
# FLASK
# ============================================================
SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")

# ============================================================
# MONGODB
# ============================================================
MONGO_URI    = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "federated_db")

# ============================================================
# NEO4J
# ============================================================
NEO4J_URI      = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# ============================================================
# BLOCKCHAIN
# ============================================================
INFURA_URL        = os.getenv("INFURA_URL")
CONTRACT_ADDRESS  = os.getenv("CONTRACT_ADDRESS")