package com.sanjuthomas.policypilot.vector;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.sanjuthomas.policypilot.TestFixtures;
import com.sanjuthomas.policypilot.neo4j.Neo4jQueryExecutor;
import com.sanjuthomas.policypilot.vector.VectorSearchService.VectorHit;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class VectorSearchServiceTest {

  @Mock Neo4jQueryExecutor neo4jQueryExecutor;

  private VectorSearchService service;

  @BeforeEach
  void setUp() {
    service = new VectorSearchService(neo4jQueryExecutor, TestFixtures.properties());
  }

  @Test
  @SuppressWarnings("unchecked")
  void searchFiltersSecurityEventsAndMapsHits() {
    when(neo4jQueryExecutor.runRead(anyString(), any()))
        .thenReturn(
            List.of(
                Map.of(
                    "node",
                    Map.of(
                        "event_id",
                        "evt-1",
                        "owning_lob",
                        "FICC",
                        "source",
                        "payment_security_event",
                        "search_text",
                        "policy denial alert",
                        "payload_json",
                        "{\"event_id\":\"evt-1\",\"source\":\"payment_security_event\","
                            + "\"authorization_summary\":\"Denied by policy\","
                            + "\"action\":\"APPROVE\",\"severity\":\"ALERT\"}"),
                    "score",
                    0.91)));

    List<VectorHit> hits =
        service.search(new float[] {0.1f, 0.2f}, 5, "security_events", Set.of("FICC"));

    assertEquals(1, hits.size());
    assertEquals("evt-1", hits.get(0).eventId());
    assertEquals("vector", hits.get(0).source());
    assertTrue(VectorSearchService.summaryFromHit(hits.get(0)).contains("Denied by policy"));

    ArgumentCaptor<Map<String, Object>> params = ArgumentCaptor.forClass(Map.class);
    verify(neo4jQueryExecutor).runRead(anyString(), params.capture());
    assertEquals(List.of("instruction_security_event", "payment_security_event"), params.getValue().get("sources"));
    assertEquals(List.of("FICC"), params.getValue().get("allowed_lobs"));
  }

  @Test
  void emptyAllowedLobsReturnsNoHits() {
    assertTrue(service.search(new float[] {1f}, 3, "security_events", Set.of()).isEmpty());
  }
}
