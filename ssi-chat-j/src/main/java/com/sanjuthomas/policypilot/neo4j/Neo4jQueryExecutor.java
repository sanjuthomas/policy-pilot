package com.sanjuthomas.policypilot.neo4j;

import com.sanjuthomas.policypilot.observability.StructuredLog;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.neo4j.driver.AccessMode;
import org.neo4j.driver.Driver;
import org.neo4j.driver.Record;
import org.neo4j.driver.Result;
import org.neo4j.driver.Session;
import org.neo4j.driver.SessionConfig;
import org.neo4j.driver.Value;
import org.neo4j.driver.types.Node;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/** Read-only Neo4j execution as svc_chat. */
@Component
public class Neo4jQueryExecutor {

  private static final Logger log = LoggerFactory.getLogger(Neo4jQueryExecutor.class);

  private final Driver driver;

  public Neo4jQueryExecutor(Driver driver) {
    this.driver = driver;
  }

  public List<Map<String, Object>> runRead(String cypher) {
    return runRead(cypher, Map.of());
  }

  public List<Map<String, Object>> runRead(String cypher, Map<String, Object> params) {
    SessionConfig config =
        SessionConfig.builder().withDefaultAccessMode(AccessMode.READ).build();
    Map<String, Object> effective = params == null ? Map.of() : params;
    long startNs = System.nanoTime();
    try (Session session = driver.session(config)) {
      List<Map<String, Object>> rows =
          session.executeRead(
              tx -> {
                Result result = tx.run(cypher, effective);
                List<Map<String, Object>> collected = new ArrayList<>();
                while (result.hasNext()) {
                  collected.add(toMap(result.next()));
                }
                return collected;
              });
      StructuredLog.debug(
          log,
          "neo4j.read.completed",
          Map.of(
              "neo4j.row_count",
              rows.size(),
              "neo4j.duration_ms",
              (System.nanoTime() - startNs) / 1_000_000.0,
              "neo4j.cypher_chars",
              cypher == null ? 0 : cypher.length()));
      return rows;
    }
  }

  private static Map<String, Object> toMap(Record record) {
    Map<String, Object> row = new LinkedHashMap<>();
    for (String key : record.keys()) {
      row.put(key, convert(record.get(key)));
    }
    return row;
  }

  private static Object convert(Value value) {
    if (value == null || value.isNull()) {
      return null;
    }
    return switch (value.type().name()) {
      case "INTEGER", "LONG" -> value.asLong();
      case "FLOAT", "DOUBLE" -> value.asDouble();
      case "BOOLEAN" -> value.asBoolean();
      case "LIST" -> {
        List<Object> list = new ArrayList<>();
        for (Value item : value.values()) {
          list.add(convert(item));
        }
        yield list;
      }
      case "MAP" -> {
        Map<String, Object> map = new LinkedHashMap<>();
        for (String key : value.keys()) {
          map.put(key, convert(value.get(key)));
        }
        yield map;
      }
      case "NODE" -> {
        Node node = value.asNode();
        Map<String, Object> map = new LinkedHashMap<>();
        for (String key : node.keys()) {
          map.put(key, convert(node.get(key)));
        }
        yield map;
      }
      default -> value.asObject();
    };
  }
}
