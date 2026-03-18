from neo4j import GraphDatabase

URI = "neo4j+ssc://98aa8238.databases.neo4j.io"
USERNAME ="98aa8238"
PASSWORD ="GeFAiTUEeDdBvetGqT4ncelPJNAs39LXH5dLbUaS-bI"

driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))

with driver.session() as session:
    result = session.run("RETURN 1 AS num")
    print(result.single()["num"])

driver.close()