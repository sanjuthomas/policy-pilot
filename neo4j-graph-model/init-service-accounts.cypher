// Neo4j Enterprise service accounts — least privilege for Policy Pilot.
// Applied by scripts/neo4j-init-users.sh against the system database as admin.
// Idempotent. Placeholders __CHAT_PASSWORD__ / __INDEXER_PASSWORD__ / __HARNESS_PASSWORD__
// are substituted by the init script.
//
// Accounts:
//   svc_chat     — read graph + execute procedures (vector search) — ssi-chat
//   svc_indexer  — write graph + schema (indexes/constraints) + procedures — ssi-indexer
//   svc_harness  — write graph for demo seed scripts (no schema management)
//
// Admin `neo4j` remains for Browser / ops (password from NEO4J_AUTH).

CREATE ROLE role_ssi_chat IF NOT EXISTS;
GRANT ACCESS ON DATABASE neo4j TO role_ssi_chat;
GRANT MATCH {*} ON GRAPH neo4j TO role_ssi_chat;
GRANT SHOW INDEX ON DATABASE neo4j TO role_ssi_chat;
GRANT SHOW CONSTRAINT ON DATABASE neo4j TO role_ssi_chat;
GRANT EXECUTE PROCEDURE * ON DBMS TO role_ssi_chat;
GRANT EXECUTE BOOSTED PROCEDURE * ON DBMS TO role_ssi_chat;
GRANT EXECUTE FUNCTION * ON DBMS TO role_ssi_chat;

CREATE ROLE role_ssi_indexer IF NOT EXISTS;
GRANT ACCESS ON DATABASE neo4j TO role_ssi_indexer;
GRANT MATCH {*} ON GRAPH neo4j TO role_ssi_indexer;
GRANT WRITE ON GRAPH neo4j TO role_ssi_indexer;
GRANT CREATE NEW NODE LABEL ON DATABASE neo4j TO role_ssi_indexer;
GRANT CREATE NEW RELATIONSHIP TYPE ON DATABASE neo4j TO role_ssi_indexer;
GRANT CREATE NEW PROPERTY NAME ON DATABASE neo4j TO role_ssi_indexer;
GRANT INDEX MANAGEMENT ON DATABASE neo4j TO role_ssi_indexer;
GRANT CONSTRAINT MANAGEMENT ON DATABASE neo4j TO role_ssi_indexer;
GRANT SHOW INDEX ON DATABASE neo4j TO role_ssi_indexer;
GRANT SHOW CONSTRAINT ON DATABASE neo4j TO role_ssi_indexer;
GRANT EXECUTE PROCEDURE * ON DBMS TO role_ssi_indexer;
GRANT EXECUTE BOOSTED PROCEDURE * ON DBMS TO role_ssi_indexer;
GRANT EXECUTE FUNCTION * ON DBMS TO role_ssi_indexer;

CREATE ROLE role_ssi_harness IF NOT EXISTS;
GRANT ACCESS ON DATABASE neo4j TO role_ssi_harness;
GRANT MATCH {*} ON GRAPH neo4j TO role_ssi_harness;
GRANT WRITE ON GRAPH neo4j TO role_ssi_harness;
GRANT CREATE NEW NODE LABEL ON DATABASE neo4j TO role_ssi_harness;
GRANT CREATE NEW RELATIONSHIP TYPE ON DATABASE neo4j TO role_ssi_harness;
GRANT CREATE NEW PROPERTY NAME ON DATABASE neo4j TO role_ssi_harness;
GRANT SHOW INDEX ON DATABASE neo4j TO role_ssi_harness;
GRANT EXECUTE PROCEDURE * ON DBMS TO role_ssi_harness;
GRANT EXECUTE BOOSTED PROCEDURE * ON DBMS TO role_ssi_harness;
GRANT EXECUTE FUNCTION * ON DBMS TO role_ssi_harness;

CREATE USER svc_chat IF NOT EXISTS SET PASSWORD '__CHAT_PASSWORD__' CHANGE NOT REQUIRED SET STATUS ACTIVE;
CREATE USER svc_indexer IF NOT EXISTS SET PASSWORD '__INDEXER_PASSWORD__' CHANGE NOT REQUIRED SET STATUS ACTIVE;
CREATE USER svc_harness IF NOT EXISTS SET PASSWORD '__HARNESS_PASSWORD__' CHANGE NOT REQUIRED SET STATUS ACTIVE;

GRANT ROLE role_ssi_chat TO svc_chat;
GRANT ROLE role_ssi_indexer TO svc_indexer;
GRANT ROLE role_ssi_harness TO svc_harness;
