from flask import Flask
from flask_login import LoginManager, UserMixin
from pymongo import MongoClient
from bson.objectid import ObjectId
from config import MONGO_URI, MONGO_DB_NAME, SECRET_KEY
import os

# ==========================================================
# FLASK APP
# ==========================================================

app = Flask(__name__)
app.secret_key = SECRET_KEY

# uploads/ folder removed — files are processed in-memory (Vercel compatible)

# ==========================================================
# DATABASE
# ==========================================================

client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]

users_collection = db["users"]
local_models_collection = db["local_models"]

# ==========================================================
# LOGIN MANAGER
# ==========================================================

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login"


class User(UserMixin):

    def __init__(self, user_data):
        self.id = str(user_data["_id"])
        self.username = user_data["username"]


@login_manager.user_loader
def load_user(user_id):
    user_data = users_collection.find_one({"_id": ObjectId(user_id)})
    if user_data:
        return User(user_data)
    return None
