package com.sanjuthomas.policypilot.vector;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.when;

import com.sanjuthomas.policypilot.TestFixtures;
import com.sanjuthomas.policypilot.api.ApiModels.SourceHit;
import com.sanjuthomas.policypilot.auth.Subject;
import com.sanjuthomas.policypilot.pipeline.LaneAnswer;
import com.sanjuthomas.policypilot.vector.VectorSearchService.VectorHit;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.embedding.EmbeddingModel;

@ExtendWith(MockitoExtension.class)
class FullRagLaneServiceTest {

  @Mock EmbeddingModel embeddingModel;
  @Mock VectorSearchService vectorSearchService;
  @Mock ChatClient.Builder chatClientBuilder;
  @Mock ChatClient chatClient;
  @Mock ChatClient.ChatClientRequestSpec requestSpec;
  @Mock ChatClient.CallResponseSpec callResponseSpec;

  private FullRagLaneService service;

  @BeforeEach
  void setUp() {
    lenient().when(chatClientBuilder.build()).thenReturn(chatClient);
    lenient().when(chatClient.prompt()).thenReturn(requestSpec);
    lenient().when(requestSpec.system(anyString())).thenReturn(requestSpec);
    lenient().when(requestSpec.user(anyString())).thenReturn(requestSpec);
    lenient().when(requestSpec.call()).thenReturn(callResponseSpec);
    service =
        new FullRagLaneService(
            embeddingModel, vectorSearchService, chatClientBuilder, TestFixtures.properties());
  }

  @Test
  void answerEmbedsSearchesAndSynthesizesFullRag() {
    when(embeddingModel.embed(anyString())).thenReturn(new float[] {0.1f, 0.2f});
    when(vectorSearchService.search(any(), anyInt(), eq("security_events"), isNull()))
        .thenReturn(
            List.of(
                new VectorHit(
                    "vector",
                    0.88,
                    "evt-9",
                    "20260720-FICC-I-1",
                    null,
                    "FICC",
                    "policy denial",
                    Map.of(
                        "action",
                        "VIEW",
                        "severity",
                        "ALERT",
                        "authorization_summary",
                        "Policy denial on VIEW"),
                    Map.of(),
                    Map.of("source", "instruction_security_event"))));
    when(callResponseSpec.content())
        .thenReturn(
            "Recent policy denial activity includes an ALERT when VIEW was denied on an instruction.");

    Subject subject =
        new Subject(
            "comp-001",
            "Comp",
            "One",
            "Analyst",
            "FICC",
            List.of("COMPLIANCE_ANALYST"),
            List.of(),
            null,
            List.of(),
            "token",
            "session");

    LaneAnswer answer =
        service.answer(
            "Write a brief narrative about recent policy denial activity in the audit log.",
            "events",
            subject);

    assertEquals("full_rag", answer.recordedPath());
    assertEquals("gemini_full", answer.synthesis());
    assertEquals("none", answer.cypherProvenance());
    assertTrue(answer.answer().toLowerCase().contains("denial"));
    assertEquals(1, answer.sources().size());
    SourceHit source = answer.sources().get(0);
    assertEquals(List.of("vector"), source.sources());
    assertEquals("evt-9", source.event_id());
  }

  @Test
  void searchSourceForModeMapsEvents() {
    assertEquals("security_events", FullRagLaneService.searchSourceForMode("events"));
    assertEquals("instruction_state", FullRagLaneService.searchSourceForMode("instructions"));
  }

  @Test
  void buildContextIncludesModeBanner() {
    String context = FullRagLaneService.buildContext(List.of(), "events");
    assertTrue(context.contains("SECURITY EVENTS"));
    assertTrue(context.contains("No indexed data was found."));
  }
}
