from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_required, logout_user, login_user, current_user
from pymongo import MongoClient
from config import MONGO_URI
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
import os
import pandas as pd
import networkx as nx
import hashlib
import json
from web3 import Web3
import json
import plotly.graph_objects as go
from neo4j import GraphDatabase

#=================================
# Neo4j connection
#=================================
URI = "neo4j+ssc://98aa8238.databases.neo4j.io"
USERNAME ="98aa8238"
PASSWORD ="GeFAiTUEeDdBvetGqT4ncelPJNAs39LXH5dLbUaS-bI"

driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))
#===========================================================
#BLOCK CHAIN SETUP
#===========================================================
from web3 import Web3

w3 = Web3(Web3.HTTPProvider(
"https://sepolia.infura.io/v3/eacc2ea3e0bf433bb2d6313b8885038d"
))

with open("blockchain/FederatedIntegrity.json") as f:
    artifact = json.load(f)

contract_abi = artifact["abi"]

contract_address = Web3.to_checksum_address(
"0x18bd1B445bDb3b0EB7e88E166E75402FB087823C"
)

contract = w3.eth.contract(
    address=contract_address,
    abi=contract_abi
)
# ==========================================================
# BLOCKCHAIN VERIFICATION
# ==========================================================
def get_blockchain_global_hash():

    try:

        events = contract.events.GlobalHashStored.get_logs(
            from_block=0,
            to_block="latest"
        )

        if not events:
            return None

        latest = events[-1]

        blockchain_hash = latest["args"]["hash"]

        return blockchain_hash

    except Exception as e:
        print("Blockchain error:", e)
        return None
# ==========================================================
# GRAPH + LEARNING FUNCTIONS
# ==========================================================

def create_graph_from_csv(filepath):

    df = pd.read_csv(filepath)

    if "diagnosis" not in df.columns:
        raise Exception("CSV must contain 'diagnosis' column")

    G = nx.DiGraph()

    for _, row in df.iterrows():

        disease = str(row["diagnosis"]).strip()

        if not disease or disease.lower() == "nan":
            continue

        for col in df.columns:
            if col not in ["patient_id", "diagnosis"]:

                symptom = row[col]

                if pd.notna(symptom):

                    symptom = str(symptom).strip()

                    if symptom and symptom.lower() != "nan":
                        G.add_edge(disease, symptom)

    return G


def extract_learning(filepath):

    df = pd.read_csv(filepath)

    symptom_cols = [
        col for col in df.columns
        if col not in ["patient_id", "diagnosis"]
    ]

    model = {}
    total_cases = len(df)

    disease_counts = df["diagnosis"].value_counts().to_dict()

    for disease, count in disease_counts.items():

        disease_df = df[df["diagnosis"] == disease]

        symptom_counter = {}

        for _, row in disease_df.iterrows():

            for col in symptom_cols:

                symptom = row[col]

                if pd.notna(symptom) and str(symptom).strip() != "":
                    symptom_counter[symptom] = symptom_counter.get(symptom, 0) + 1

        symptom_strength = {}

        for symptom, sym_count in symptom_counter.items():

            strength = sym_count / count

            symptom_strength[symptom] = round(strength, 3)

        model[disease] = {
            "probability": round(count / total_cases, 3),
            "symptoms": symptom_strength
        }

    return model


def generate_adjacency_matrix(G):

    nodes = sorted(G.nodes())
    adj = nx.to_numpy_array(G, nodelist=nodes)

    return adj, nodes


def generate_model_hash(model_object):

    model_string = json.dumps(model_object, sort_keys=True)

    return hashlib.sha256(model_string.encode()).hexdigest()


# ==========================================================
# FEDERATED AVERAGING
# ==========================================================

def federated_average(local_models):

    temp = {}

    for model in local_models:

        for disease, values in model.items():

            if disease not in temp:
                temp[disease] = {"prob_list": [], "symptoms": {}}

            temp[disease]["prob_list"].append(values["probability"])

            for symptom, strength in values["symptoms"].items():

                if symptom not in temp[disease]["symptoms"]:
                    temp[disease]["symptoms"][symptom] = []

                temp[disease]["symptoms"][symptom].append(strength)

    global_model = {}

    for disease, values in temp.items():

        avg_prob = sum(values["prob_list"]) / len(values["prob_list"])

        avg_symptoms = {}

        for symptom, strengths in values["symptoms"].items():

            avg_strength = sum(strengths) / len(strengths)

            avg_symptoms[symptom] = round(avg_strength, 3)

        global_model[disease] = {
            "probability": round(avg_prob, 3),
            "symptoms": avg_symptoms
        }

    return global_model


def build_graph_from_learning(learning_model):

    G = nx.DiGraph()

    for disease, values in learning_model.items():

        for symptom in values["symptoms"]:
            G.add_edge(disease, symptom)

    return G


# ==========================================================
# NEO4J INTEGRATION
# ==========================================================

def push_to_global_graph(global_model, cycle_number):

    root = "GlobalFederatedGraph"

    with driver.session() as session:

        # merge by cycle rather than name to avoid overwriting previous cycles
        session.run("""
            MERGE (f:FederatedModel {cycle:$cycle})
            SET f.name = $name
        """, name=root, cycle=cycle_number)

        for disease, values in global_model.items():

            session.run("""
                MATCH (f:FederatedModel {cycle:$cycle})

                MERGE (d:Disease {name:$d, cycle:$cycle})
                SET d.probability = $prob

                MERGE (f)-[:HAS_DISEASE]->(d)
            """,
            root=root,
            d=disease,
            cycle=cycle_number,
            prob=values["probability"]
            )

            for symptom, strength in values["symptoms"].items():

                session.run("""
                    MATCH (d:Disease {name:$d, cycle:$cycle})

                    MERGE (s:Symptom {name:$s})

                    MERGE (d)-[r:HAS_SYMPTOM]->(s)
                    SET r.strength = $str
                """,
                d=disease,
                cycle=cycle_number,
                s=symptom,
                str=strength
                )


def fetch_global_graph_from_neo4j(cycle_number):

    edges = []
    learning = {}

    with driver.session() as session:

        result = session.run("""
            MATCH (f:FederatedModel {cycle:$cycle})
            -[:HAS_DISEASE]->(d:Disease {cycle:$cycle})
            -[r:HAS_SYMPTOM]->(s:Symptom)

            RETURN d.name AS disease,
                   d.probability AS probability,
                   s.name AS symptom,
                   r.strength AS strength
        """, cycle=cycle_number)

        for record in result:

            disease = record["disease"]
            probability = record["probability"]
            symptom = record["symptom"]
            strength = record["strength"]

            edges.append((disease, symptom, {"weight": strength}))

            if disease not in learning:
                learning[disease] = {
                    "probability": probability,
                    "symptoms": {}
                }

            learning[disease]["symptoms"][symptom] = strength
        
    
    return edges, learning


def get_latest_cycle():

    with driver.session() as session:

        result = session.run("""
            MATCH (f:FederatedModel)
            RETURN MAX(f.cycle) AS latest_cycle
        """)

        record = result.single()

        if record and record["latest_cycle"] is not None:
            return record["latest_cycle"]

    return 0


# ==========================================================
# LOCAL vs GLOBAL COMPARISON
# ==========================================================

def compare_local_global(local_learning, global_learning):

    new_diseases = []
    new_symptoms = []
    new_relationships = []

    if not local_learning or not global_learning:
        return new_diseases, new_symptoms, new_relationships

    local_diseases = set(local_learning.keys())
    global_diseases = set(global_learning.keys())

    new_diseases = list(global_diseases - local_diseases)

    for disease, values in global_learning.items():

        global_symptoms = set(values["symptoms"].keys())

        local_symptoms = set()

        if disease in local_learning:
            local_symptoms = set(local_learning[disease]["symptoms"].keys())

        diff = global_symptoms - local_symptoms

        for s in diff:
            new_symptoms.append(s)
            new_relationships.append((disease, s))

    return new_diseases, new_symptoms, new_relationships


# ==========================================================
# GRAPH VISUALIZATION
# ==========================================================

def hierarchical_layout(G):

    pos = {}

    root = "Medical Knowledge"
    diseases = [n for n in G.nodes() if n != root and G.out_degree(n) > 0]
    symptoms = [n for n in G.nodes() if G.out_degree(n) == 0]

    # Position root node at the top center
    if root in G.nodes():
        pos[root] = (len(diseases) * 2, 8)

    # Position diseases in the middle level, spaced evenly
    disease_spacing = max(6, len(symptoms) * 4 / len(diseases) if diseases else 6)
    for i, disease in enumerate(diseases):
        pos[disease] = (i * disease_spacing, 4)

    # Position symptoms at the bottom, spaced evenly
    symptom_spacing = 4
    for i, symptom in enumerate(symptoms):
        pos[symptom] = (i * symptom_spacing, 0)

    return pos


def visualize_graph(edges):

    G = nx.DiGraph()
    G.add_edges_from(edges)

    # Add root node and connect all diseases to it
    root = "Medical Knowledge"
    G.add_node(root)
    diseases = [n for n in G.nodes() if n != root and G.out_degree(n) > 0]
    for disease in diseases:
        G.add_edge(root, disease)

    pos = hierarchical_layout(G)

    edge_x, edge_y = [], []

    for edge in G.edges():

        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]

        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        line=dict(width=1, color="gray"),
        hoverinfo="none",
        mode="lines"
    )

    node_x, node_y, node_text, node_color = [], [], [], []

    for node in G.nodes():

        x, y = pos[node]

        node_x.append(x)
        node_y.append(y)
        node_text.append(node)

        if node == root:
            node_color.append("#FF6B6B")  # Red color for root
        elif G.out_degree(node) > 0 and node != root:
            node_color.append("orange")  # Diseases
        else:
            node_color.append("skyblue")  # Symptoms

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=node_text,
        textposition="middle center",
        marker=dict(size=80, color=node_color)
    )

    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(showlegend=False, height=600)

    return fig.to_html(full_html=False)


# ==========================================================
# COMPARISON GRAPH
# ==========================================================

def generate_comparison_graph(local_learning, global_learning):

    if not local_learning or not global_learning:
        return None

    G_local = build_graph_from_learning(local_learning)
    G_global = build_graph_from_learning(global_learning)

    new_diseases, new_symptoms, new_relationships = compare_local_global(
        local_learning, global_learning
    )

    new_edges = set(new_relationships)

    # Add root node and connect all diseases to it
    root = "Medical Knowledge"
    G_global.add_node(root)
    diseases = [n for n in G_global.nodes() if n != root and G_global.out_degree(n) > 0]
    for disease in diseases:
        G_global.add_edge(root, disease)

    pos = hierarchical_layout(G_global)

    # Separate old and new edges
    old_edges = [edge for edge in G_global.edges() if edge not in new_edges and edge[0] != root]
    new_edges_list = list(new_edges)

    # Old edges trace - grey
    edge_x_old, edge_y_old = [], []
    for edge in old_edges:
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x_old += [x0, x1, None]
        edge_y_old += [y0, y1, None]

    edge_trace_old = go.Scatter(
        x=edge_x_old,
        y=edge_y_old,
        line=dict(width=2, color="grey"),
        hoverinfo="none",
        mode="lines"
    )

    # New edges trace - green
    edge_x_new, edge_y_new = [], []
    for edge in new_edges_list:
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x_new += [x0, x1, None]
        edge_y_new += [y0, y1, None]

    edge_trace_new = go.Scatter(
        x=edge_x_new,
        y=edge_y_new,
        line=dict(width=2, color="green"),
        hoverinfo="none",
        mode="lines"
    )

    # Root edges trace - light gray
    root_edges = [edge for edge in G_global.edges() if edge[0] == root]
    edge_x_root, edge_y_root = [], []
    for edge in root_edges:
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x_root += [x0, x1, None]
        edge_y_root += [y0, y1, None]

    edge_trace_root = go.Scatter(
        x=edge_x_root,
        y=edge_y_root,
        line=dict(width=1, color="lightgray"),
        hoverinfo="none",
        mode="lines"
    )

    node_x, node_y, node_text, node_color = [], [], [], []

    for node in G_global.nodes():

        x, y = pos[node]

        node_x.append(x)
        node_y.append(y)
        node_text.append(node)

        if node == root:
            node_color.append("#FF6B6B")  # Red color for root
        elif node in new_diseases:
            node_color.append("green")
        elif node in new_symptoms:
            node_color.append("pink")
        else:
            node_color.append("orange" if G_global.out_degree(node) > 0 and node != root else "skyblue")

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=node_text,
        textposition="middle center",
        marker=dict(size=80, color=node_color)
    )

    fig = go.Figure(data=[edge_trace_root, edge_trace_old, edge_trace_new, node_trace])
    fig.update_layout(showlegend=False, height=600)

    return fig.to_html(full_html=False)


# ==========================================================
# FLASK SETUP
# ==========================================================

app = Flask(__name__)
app.secret_key = "supersecretkey"

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


# ==========================================================
# DATABASE
# ==========================================================

client = MongoClient(MONGO_URI)
db = client["federated_db"]

users_collection = db["users"]
local_models_collection = db["local_models"]

# ==========================================================
# LOGIN MANAGER
# ==========================================================

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


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


# ==========================================================
# ROUTES
# ==========================================================

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))
@app.route("/login", methods=["GET","POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        user = users_collection.find_one({"username": username})

        if user and check_password_hash(user["password"], password):

            login_user(User(user))
            return redirect(url_for("dashboard"))

        flash("Invalid username or password")

    return render_template("login.html")


@app.route("/signup", methods=["GET","POST"])
def signup():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        existing = users_collection.find_one({"username": username})

        if existing:
            flash("Username already exists")
            return redirect(url_for("signup"))

        hashed_pw = generate_password_hash(password)

        users_collection.insert_one({
            "username": username,
            "password": hashed_pw,
            "role": "observer",
            "wallet": None,
            "approved": False
        })

        flash("Account created successfully")

        return redirect(url_for("login"))

    return render_template("signup.html")



@app.route("/dashboard")
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

    # ---------------- RENDER DASHBOARD ----------------
    return render_template(
        "dashboard.html",
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


@app.route("/request_participation", methods=["POST"])
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

    return redirect(url_for("dashboard"))


@app.route("/upload", methods=["POST"])
@login_required
def upload_file():

    user = users_collection.find_one({"username": current_user.username})

    if user.get("role") != "participant":
        flash("Only approved participants can upload datasets.")
        return redirect(url_for("dashboard"))

    file = request.files["file"]

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)

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

    return redirect(url_for("dashboard"))

@app.route("/federate")
@login_required
def federate():

    user = users_collection.find_one({"username": current_user.username})

    if user.get("role") != "owner":
        flash("Only the system owner can run federated aggregation.")
        return redirect(url_for("dashboard"))

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
        return redirect(url_for("dashboard"))

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

    # Store global graph
    push_to_global_graph(global_learning, cycle_number)

    flash(f"Federated aggregation completed for Cycle {cycle_number}")

    return redirect(url_for("dashboard"))
@app.route("/approve_participants")
@login_required
def approve_participants():

    user = users_collection.find_one({"username": current_user.username})

    if user.get("role") != "owner":
        flash("Only owner can manage participants.")
        return redirect(url_for("dashboard"))

    pending_participants = list(users_collection.find({
        "role": "observer",
        "wallet": {"$ne": None},
        "approved": False
    }))

    approved_participants = list(users_collection.find({
        "role": "participant",
        "approved": True
    }))
    participants = list(users_collection.find({
        "role": "observer",
        "approved": False
    }))

    return render_template(
    "approve_participants.html",
    pending=pending_participants,
    approved=approved_participants,
    pending_count=len(participants),
    rejected_users=[]
)
@app.route("/remove_participant/<username>", methods=["POST"])
@login_required
def remove_participant(username):

    user = users_collection.find_one({"username": current_user.username})

    if user.get("role") != "owner":
        flash("Only owner can remove participants.")
        return redirect(url_for("dashboard"))

    users_collection.update_one(
        {"username": username},
        {
            "$set": {
                "role": "observer",
                "approved": False
            }
        }
    )

    flash(f"{username} removed from participant role.")

    return redirect(url_for("approve_participants"))
@app.route("/get_user_status")
@login_required
def get_user_status():
    user = users_collection.find_one({"username": current_user.username})
    return {
        "role": user.get("role", "observer"),
        "approved": user.get("approved", False)
    }

@app.route("/get_pending_count")
@login_required
def get_pending_count():

    pending = users_collection.count_documents({
        "role": "participant",
        "approved": False
    })

    return {"pending": pending}
@app.route("/approve_participant/<username>", methods=["POST"])
@login_required
def approve_participant(username):
    # Only owner can access this
    user = users_collection.find_one({"username": current_user.username})
    if user.get("role") != "owner":
        flash("Only the system owner can approve participants.")
        return redirect(url_for("dashboard"))
    
    # Approve the participant and set role to participant
    users_collection.update_one(
        {"username": username},
        {"$set": {"approved": True, "role": "participant"}}
    )
    
    flash(f"Participant {username} has been approved!")
    return redirect(url_for("approve_participants"))


@app.route("/get_local_hash")
@login_required
def get_local_hash():

    local_model = local_models_collection.find_one({
        "username": current_user.username
    })

    if not local_model:
        return jsonify({"error":"Local model not found"})

    learning = local_model["learning"]

    hash_value = hashlib.sha256(
        json.dumps(learning,sort_keys=True).encode()
    ).hexdigest()

    return jsonify({"hash":hash_value})

@app.route("/get_global_hash")
@login_required
def get_global_hash():

    latest_cycle = get_latest_cycle()

    edges, learning = fetch_global_graph_from_neo4j(latest_cycle)

    if not learning:
        return jsonify({"error":"Global model not found"})

    hash_value = hashlib.sha256(
        json.dumps(learning,sort_keys=True).encode()
    ).hexdigest()

    return jsonify({
        "hash":hash_value,
        "cycle":latest_cycle
    })
if __name__ == "__main__":
    app.run(debug=True)