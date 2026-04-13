import hashlib
import json
from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from extensions import users_collection, local_models_collection
from neo4j_utils import get_latest_cycle, fetch_global_graph_from_neo4j

api_bp = Blueprint("api", __name__)

# ==========================================================
# API ROUTES
# ==========================================================

@api_bp.route("/get_user_status")
@login_required
def get_user_status():
    user = users_collection.find_one({"username": current_user.username})
    return {
        "role": user.get("role", "observer"),
        "approved": user.get("approved", False)
    }


@api_bp.route("/get_pending_count")
@login_required
def get_pending_count():

    pending = users_collection.count_documents({
        "role": "participant",
        "approved": False
    })

    return {"pending": pending}


@api_bp.route("/get_local_hash")
@login_required
def get_local_hash():

    local_model = local_models_collection.find_one({
        "username": current_user.username
    })

    if not local_model:
        return jsonify({"error": "Local model not found"})

    learning = local_model["learning"]

    hash_value = hashlib.sha256(
        json.dumps(learning, sort_keys=True).encode()
    ).hexdigest()

    return jsonify({"hash": hash_value})


@api_bp.route("/get_global_hash")
@login_required
def get_global_hash():

    from extensions import db
    latest_cycle = get_latest_cycle()
    next_cycle = latest_cycle + 1

    pending_model = db.pending_global_models.find_one({"cycle": next_cycle})
    if pending_model:
        return jsonify({
            "hash": pending_model["hash"],
            "cycle": next_cycle,
            "is_pending": True
        })

    edges, learning = fetch_global_graph_from_neo4j(latest_cycle)

    if not learning:
        return jsonify({"error": "Global model not found"})

    hash_value = hashlib.sha256(
        json.dumps(learning, sort_keys=True).encode()
    ).hexdigest()

    return jsonify({
        "hash": hash_value,
        "cycle": latest_cycle,
        "is_pending": False
    })
