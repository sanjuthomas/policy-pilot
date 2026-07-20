package com.sanjuthomas.policypilot.eligibility;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

import com.sanjuthomas.policypilot.TestFixtures;
import com.sanjuthomas.policypilot.auth.FakeZitadelAuthClient;
import com.sanjuthomas.policypilot.auth.ServiceIdentity;
import com.sanjuthomas.policypilot.config.ChatJProperties;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.server.ResponseStatusException;

class EligibilityClientTest {

  private RestTemplate restTemplate;
  private MockRestServiceServer server;
  private EligibilityClient client;

  @BeforeEach
  void setUp() {
    ChatJProperties properties = TestFixtures.properties();
    FakeZitadelAuthClient zitadel =
        new FakeZitadelAuthClient()
            .onLogin(
                (login, password) ->
                    new com.sanjuthomas.policypilot.auth.SessionCredentials("svc-sess", "svc-tok", "svc"));
    ServiceIdentity serviceIdentity = new ServiceIdentity(zitadel, properties);
    serviceIdentity.ensureLoggedIn(1, 0L);

    restTemplate = new RestTemplateBuilder().build();
    server = MockRestServiceServer.bindTo(restTemplate).build();
    client = new EligibilityClient(restTemplate, properties, serviceIdentity);
  }

  @Test
  void eligibleApproversForInstructionReturnsBody() {
    server
        .expect(requestTo("http://instruction:8000/api/v1/instructions/INS-1/eligible-approvers"))
        .andExpect(method(HttpMethod.POST))
        .andRespond(
            withSuccess("{\"instruction_id\":\"INS-1\"}", MediaType.APPLICATION_JSON));

    assertEquals(
        "INS-1",
        client
            .eligibleApproversForInstruction("INS-1", "user-tok", "user-sess")
            .get("instruction_id"));
    server.verify();
  }

  @Test
  void eligibleApproversForPaymentReturnsBody() {
    server
        .expect(requestTo("http://payment:8093/api/v1/payments/PAY-1/eligible-approvers"))
        .andExpect(method(HttpMethod.POST))
        .andRespond(withSuccess("{\"payment_id\":\"PAY-1\"}", MediaType.APPLICATION_JSON));

    assertEquals("PAY-1", client.eligibleApproversForPayment("PAY-1", "user-tok", "user-sess").get("payment_id"));
    server.verify();
  }

  @Test
  void eligibleApproversForPaymentReturnsEmptyWhenBodyNull() {
    server
        .expect(requestTo("http://payment:8093/api/v1/payments/PAY-2/eligible-approvers"))
        .andRespond(withSuccess("", MediaType.APPLICATION_JSON));

    assertEquals(java.util.Map.of(), client.eligibleApproversForPayment("PAY-2", "user-tok", "user-sess"));
    server.verify();
  }

  @Test
  void eligibleSubmittersForPaymentLoadsPaymentThenAuthz() {
    server
        .expect(requestTo("http://payment:8093/api/v1/payments/PAY-1"))
        .andExpect(method(HttpMethod.GET))
        .andRespond(
            withSuccess(
                """
                {"payment_id":"PAY-1","instruction_id":"INS-1","status":"DRAFT",
                 "amount":10,"currency":"USD","owning_lob":"FICC",
                 "created_by":{"user_id":"mo-100"}}
                """,
                MediaType.APPLICATION_JSON));
    server
        .expect(requestTo("http://instruction:8000/api/v1/instructions/INS-1"))
        .andExpect(method(HttpMethod.GET))
        .andRespond(
            withSuccess(
                "{\"instruction_id\":\"INS-1\",\"status\":\"APPROVED\",\"end_date\":\"2026-12-31\"}",
                MediaType.APPLICATION_JSON));
    server
        .expect(
            requestTo("http://authz:8094/api/v1/authorization/payments/eligible-submitters"))
        .andExpect(method(HttpMethod.POST))
        .andRespond(
            withSuccess(
                "{\"payment_id\":\"PAY-1\",\"eligible\":[],\"candidates_evaluated\":1}",
                MediaType.APPLICATION_JSON));

    assertEquals(
        "PAY-1",
        client.eligibleSubmittersForPayment("PAY-1", "user-tok", "user-sess").get("payment_id"));
    server.verify();
  }

  @Test
  void maps401ToUnauthorized() {
    server
        .expect(requestTo("http://payment:8093/api/v1/payments/PAY-1/eligible-approvers"))
        .andRespond(withStatus(HttpStatus.UNAUTHORIZED));

    ResponseStatusException ex =
        assertThrows(
            ResponseStatusException.class,
            () -> client.eligibleApproversForPayment("PAY-1", "user-tok", "user-sess"));
    assertEquals(HttpStatus.UNAUTHORIZED, ex.getStatusCode());
  }

  @Test
  void maps403ToForbidden() {
    server
        .expect(requestTo("http://payment:8093/api/v1/payments/PAY-1/eligible-approvers"))
        .andRespond(withStatus(HttpStatus.FORBIDDEN).body("denied"));

    ResponseStatusException ex =
        assertThrows(
            ResponseStatusException.class,
            () -> client.eligibleApproversForPayment("PAY-1", "user-tok", "user-sess"));
    assertEquals(HttpStatus.FORBIDDEN, ex.getStatusCode());
    assertEquals("denied", ex.getReason());
  }

  @Test
  void maps404ToNotFound() {
    server
        .expect(requestTo("http://payment:8093/api/v1/payments/PAY-1/eligible-approvers"))
        .andRespond(withStatus(HttpStatus.NOT_FOUND).body("missing"));

    ResponseStatusException ex =
        assertThrows(
            ResponseStatusException.class,
            () -> client.eligibleApproversForPayment("PAY-1", "user-tok", "user-sess"));
    assertEquals(HttpStatus.NOT_FOUND, ex.getStatusCode());
  }

  @Test
  void mapsOtherErrorsToBadGateway() {
    server
        .expect(requestTo("http://payment:8093/api/v1/payments/PAY-1/eligible-approvers"))
        .andRespond(withStatus(HttpStatus.BAD_GATEWAY).body("upstream"));

    ResponseStatusException ex =
        assertThrows(
            ResponseStatusException.class,
            () -> client.eligibleApproversForPayment("PAY-1", "user-tok", "user-sess"));
    assertEquals(HttpStatus.BAD_GATEWAY, ex.getStatusCode());
  }

  @Test
  void paymentAmountLimitsReturnsBody() {
    server
        .expect(requestTo("http://authz:8094/api/v1/authorization/payment-amount-limits"))
        .andExpect(method(HttpMethod.GET))
        .andRespond(
            withSuccess(
                "{\"absolute_limit\":100000000000,\"club_limits\":{\"UP_TO_100_BILLION_CLUB\":100000000000}}",
                MediaType.APPLICATION_JSON));

    var body = client.paymentAmountLimits("user-tok", "user-sess");
    assertEquals(100_000_000_000.0, ((Number) body.get("absolute_limit")).doubleValue());
  }

  @Test
  void groupMembersEncodesPathAndQuery() {
    server
        .expect(
            requestTo(
                "http://authz:8094/api/v1/authorization/groups/UP_TO_100_BILLION_CLUB/members?role=FUNDING_APPROVER"))
        .andExpect(method(HttpMethod.GET))
        .andRespond(
            withSuccess(
                "{\"group\":\"UP_TO_100_BILLION_CLUB\",\"members\":[{\"user_id\":\"pay-204\"}]}",
                MediaType.APPLICATION_JSON));

    var body =
        client.groupMembers(
            "UP_TO_100_BILLION_CLUB", "user-tok", "user-sess", "FUNDING_APPROVER", null);
    assertEquals("UP_TO_100_BILLION_CLUB", body.get("group"));
  }

  @Test
  void groupMembersIncludesCoveringLobQuery() {
    server
        .expect(
            requestTo(
                "http://authz:8094/api/v1/authorization/groups/MIDDLE_OFFICE/members?role=FUNDING_APPROVER&covering_lob=FICC"))
        .andExpect(method(HttpMethod.GET))
        .andRespond(
            withSuccess(
                "{\"group\":\"MIDDLE_OFFICE\",\"members\":[{\"user_id\":\"pay-201\"}]}",
                MediaType.APPLICATION_JSON));

    var body =
        client.groupMembers("MIDDLE_OFFICE", "user-tok", "user-sess", "FUNDING_APPROVER", "FICC");
    assertEquals("MIDDLE_OFFICE", body.get("group"));
  }
}
