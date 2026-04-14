from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
# ==========================================================
# NEO4J CONNECTION
# ==========================================================

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

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
