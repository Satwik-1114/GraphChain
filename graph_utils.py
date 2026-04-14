import pandas as pd
import networkx as nx
import hashlib
import json
import plotly.graph_objects as go

# ==========================================================
# GRAPH + LEARNING FUNCTIONS
# ==========================================================

def create_graph_from_csv(source):
    """Accept a filepath string or a file-like buffer (io.StringIO / io.BytesIO)."""

    df = pd.read_csv(source)

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


def extract_learning(source):
    """Accept a filepath string or a file-like buffer (io.StringIO / io.BytesIO)."""

    df = pd.read_csv(source)

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
