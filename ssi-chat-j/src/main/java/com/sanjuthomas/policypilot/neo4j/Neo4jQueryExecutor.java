package com.sanjuthomas.policypilot.neo4j;

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
import org.springframework.stereotype.Component;

/** Read-only Neo4j execution as svc_chat. */
@Component
public class Neo4jQueryExecutor {

  private final Driver driver;

  public Neo4jQueryExecutor(Driver driver) {
    this.driver = driver;
  }

  public List<Map<String, Object>> runRead(String cypher) {
    SessionConfig config =
        SessionConfig.builder().withDefaultAccessMode(AccessMode.READ).build();
    try (Session session = driver.session(config)) {
      return session.executeRead(
          tx -> {
            Result result = tx.run(cypher);
            List<Map<String, Object>> rows = new ArrayList<>();
            while (result.hasNext()) {
              rows.add(toMap(result.next()));
            }
            return rows;
          });
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
      default -> value.asObject();
    };
  }
}
