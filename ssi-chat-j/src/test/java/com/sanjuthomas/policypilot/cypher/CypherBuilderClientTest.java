package com.sanjuthomas.policypilot.cypher;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

import com.sanjuthomas.policypilot.TestFixtures;
import com.sanjuthomas.policypilot.cypher.CypherBuilderModels.PlanResponse;
import com.sanjuthomas.policypilot.cypher.CypherBuilderModels.ValidateResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestTemplate;

class CypherBuilderClientTest {

  private RestTemplate restTemplate;
  private MockRestServiceServer server;
  private CypherBuilderClient client;

  @BeforeEach
  void setUp() {
    restTemplate = new RestTemplate();
    server = MockRestServiceServer.createServer(restTemplate);
    client = new CypherBuilderClient(restTemplate, TestFixtures.properties());
  }

  @Test
  void planDeserializesSnakeCaseIntentId() {
    server
        .expect(requestTo("http://cypher-builder:8097/v1/plan"))
        .andExpect(method(HttpMethod.POST))
        .andRespond(
            withSuccess(
                """
                {"matched":true,"intent_id":"planned_graph","strategy":"neo4j_direct",
                 "planned":[{"label":"count","cypher":"MATCH (e) RETURN 1"}],
                 "meta":{"cypher_class":"deterministic"}}
                """,
                MediaType.APPLICATION_JSON));

    PlanResponse response = client.plan("How many ALERT events happened today?", "events");
    assertTrue(response.matched());
    assertEquals("planned_graph", response.intentId());
    assertEquals("count", response.planned().get(0).label());
    server.verify();
  }

  @Test
  void validateOk() {
    server
        .expect(requestTo("http://cypher-builder:8097/v1/validate"))
        .andExpect(method(HttpMethod.POST))
        .andRespond(
            withSuccess(
                """
                {"ok":true,"cypher":"MATCH (e) RETURN 1 LIMIT 1","error":null}
                """,
                MediaType.APPLICATION_JSON));

    ValidateResponse response = client.validate("MATCH (e) RETURN 1");
    assertTrue(response.ok());
    assertEquals("MATCH (e) RETURN 1 LIMIT 1", response.cypher());
    server.verify();
  }
}
