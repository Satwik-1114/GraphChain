import os
import networkx as nx
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import users_collection, local_models_collection, app as flask_app, db
from neo4j_utils import get_latest_cycle, fetch_global_graph_from_neo4j, push_to_global_graph
from blockchain_utils import get_blockchain_global_hash
from graph_utils import (
    create_graph_from_csv,
    extract_learning,
    generate_adjacency_matrix,
    generate_model_hash,
    visualize_graph,
    compare_local_global,
    generate_comparison_graph,
    federated_average,
)

dashboard_bp = Blueprint("dashboard", __name__)

# ==========================================================
# DASHBOARD
# ==========================================================

@dashboard_bp.route("/dashboard")
@login_required
def dashboard():

    user = users_collection.find_one({"username": current_user.username})

    role = user.get("role", "observer")
    approved = user.get("approved", False)

    local_model = local_models_collection.find_one({"username": current_user.username})

    # Fetch global model from Neo4j
    latest_cycle = get_latest_cycle()
    global_edges = []
    global_learning = {}

    if latest_cycle == 0:
        global_verified = False
    else:
        global_edges, global_learning = fetch_global_graph_from_neo4j(cycle_number=latest_cycle)
        neo4j_hash = generate_model_hash(global_learning)
        blockchain_hash = get_blockchain_global_hash()
        if blockchain_hash and neo4j_hash:
            global_verified = (blockchain_hash == neo4j_hash)
            print(global_verified, blockchain_hash, neo4j_hash)
        else:
            global_verified = False

    graph_html = None
    global_graph_html = None
    comparison_graph_html = None

    local_stats = {}
    global_stats = {}

    local_learning = None

    new_diseases = []
    new_symptoms = []
    new_relationships = []

    # ---------------- LOCAL GRAPH ----------------

    if local_model:

        edges = local_model.get("edges", [])
        local_learning = local_model.get("learning", {})

        G_local = nx.DiGraph()
        G_local.add_edges_from(edges)

        diseases = [n for n in G_local.nodes() if G_local.out_degree(n) > 0]
        symptoms = [n for n in G_local.nodes() if G_local.out_degree(n) == 0]

        local_stats = {
            "diseases": len(diseases),
            "symptoms": len(symptoms),
            "relationships": len(G_local.edges())
        }

        graph_html = visualize_graph(edges)

    # ---------------- GLOBAL GRAPH ----------------

    if global_edges and global_verified:

        simple_edges = [(e[0], e[1]) for e in global_edges]

        G_global = nx.DiGraph()
        G_global.add_edges_from(simple_edges)

        diseases = [n for n in G_global.nodes() if G_global.out_degree(n) > 0]
        symptoms = [n for n in G_global.nodes() if G_global.out_degree(n) == 0]

        global_stats = {
            "diseases": len(diseases),
            "symptoms": len(symptoms),
            "relationships": len(G_global.edges())
        }

        global_graph_html = visualize_graph(simple_edges)

    # ---------------- DISCOVERY COMPARISON ----------------

    if local_learning and global_learning and global_verified:

        new_diseases, new_symptoms, new_relationships = compare_local_global(
            local_learning,
            global_learning
        )

        comparison_graph_html = generate_comparison_graph(
            local_learning,
            global_learning
        )

    elif role == "owner" and global_learning:
        new_diseases = list(global_learning.keys())

    pending_model = db.pending_global_models.find_one({"cycle": latest_cycle + 1})
    has_pending_model = pending_model is not None

    # ---------------- RENDER DASHBOARD ----------------
    return render_template(
        "dashboard.html",
        has_pending_model=has_pending_model,
        username=current_user.username,
        role=role,
        approved=approved,
        wallet=user.get("wallet"),
        cycle_number=latest_cycle,
        graph_html=graph_html,
        global_graph_html=global_graph_html,
        comparison_graph_html=comparison_graph_html,
        local_stats=local_stats,
        global_stats=global_stats,
        local_learning=local_learning,
        global_learning=global_learning,
        new_diseases=new_diseases,
        new_symptoms=new_symptoms,
        new_relationships=new_relationships,
        global_verified=global_verified,
    )


# ==========================================================
# REQUEST PARTICIPATION
# ==========================================================

@dashboard_bp.route("/request_participation", methods=["POST"])
@login_required
def request_participation():

    wallet = request.form["wallet"]

    users_collection.update_one(
        {"username": current_user.username},
        {
            "$set": {
                "wallet": wallet,
                "approved": False,
                "role": "observer"
            }
        }
    )

    flash("Participation request sent to system owner.")
    return redirect(url_for("dashboard.dashboard"))


# ==========================================================
# UPLOAD
# ==========================================================

@dashboard_bp.route("/upload", methods=["POST"])
@login_required
def upload_file():

    user = users_collection.find_one({"username": current_user.username})

    if user.get("role") != "participant":
        flash("Only approved participants can upload datasets.")
        return redirect(url_for("dashboard.dashboard"))

    file = request.files["file"]

    filepath = os.path.join(flask_app.config["UPLOAD_FOLDER"], file.filename)

    file.save(filepath)

    G = create_graph_from_csv(filepath)

    learning = extract_learning(filepath)

    adj, nodes = generate_adjacency_matrix(G)

    hash_object = {
        "learning": learning,
        "adjacency": adj.tolist()
    }

    model_hash = generate_model_hash(hash_object)

    local_models_collection.update_one(
        {"username": current_user.username},
        {
            "$set": {
                "edges": list(G.edges()),
                "learning": learning,
                "adjacency": adj.tolist(),
                "hash": model_hash
            }
        },
        upsert=True
    )

    flash("Local model processed successfully.")
    return redirect(url_for("dashboard.dashboard"))


# ==========================================================
# FEDERATE
# ==========================================================

@dashboard_bp.route("/federate")
@login_required
def federate():

    user = users_collection.find_one({"username": current_user.username})

    if user.get("role") != "owner":
        flash("Only the system owner can run federated aggregation.")
        return redirect(url_for("dashboard.dashboard"))

    # Get approved participants
    approved_users = users_collection.find({
        "role": "participant",
        "approved": True
    })

    approved_usernames = [u["username"] for u in approved_users]

    # Fetch local models
    all_models = list(local_models_collection.find({
        "username": {"$in": approved_usernames}
    }))

    learning_models = []

    for model in all_models:
        if "learning" in model:
            learning_models.append(model["learning"])

    # Check if models exist
    if len(learning_models) == 0:
        flash("Participants have not uploaded models yet.")
        return redirect(url_for("dashboard.dashboard"))

    print("🚀 Running Federated Aggregation")
    print("Participants:", len(learning_models))

    # Federated averaging
    global_learning = federated_average(learning_models)

    # Generate hash
    global_hash = generate_model_hash(global_learning)

    # ---------------- BLOCKCHAIN VERIFICATION ----------------
    blockchain_hash = get_blockchain_global_hash()

    if blockchain_hash and global_hash:
        global_verified = (blockchain_hash == global_hash)
    else:
        global_verified = False

    # Compute cycle
    cycle_number = get_latest_cycle() + 1

    print("New Cycle:", cycle_number)

    # Store global graph in PENDING collection instead of Neo4j
    db.pending_global_models.update_one(
        {"cycle": cycle_number},
        {"$set": {
            "learning": global_learning,
            "hash": global_hash,
            "created_by": current_user.username
        }},
        upsert=True
    )

    flash(f"Federated aggregation prepared for Cycle {cycle_number}. Please Sign Global Model Hash to complete.")
    return redirect(url_for("dashboard.dashboard"))

# ==========================================================
# PUSH PENDING GLOBAL
# ==========================================================

@dashboard_bp.route("/push_pending_global", methods=["POST"])
@login_required
def push_pending_global():

    user = users_collection.find_one({"username": current_user.username})

    if user.get("role") != "owner":
        return {"error": "Unauthorized"}, 403

    cycle_number = get_latest_cycle() + 1
    pending_model = db.pending_global_models.find_one({"cycle": cycle_number})

    if not pending_model:
        return {"error": "No pending model found to push"}, 404

    print("Pushing pending global model to Neo4j for Cycle", cycle_number)
    push_to_global_graph(pending_model["learning"], cycle_number)
    
    # Remove from pending after successful push
    db.pending_global_models.delete_one({"cycle": cycle_number})

    return {"success": True}
