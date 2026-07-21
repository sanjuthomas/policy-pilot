package com.sanjuthomas.policypilot.service;

import com.sanjuthomas.policypilot.api.ApiModels.ChatRequest;
import com.sanjuthomas.policypilot.api.ApiModels.ChatResponse;
import com.sanjuthomas.policypilot.auth.Subject;

public class FakeChatService extends ChatService {

  private ChatResponse response = ChatResponse.of("default", null);

  public FakeChatService() {
    super(null, null, null);
  }

  public FakeChatService returning(ChatResponse response) {
    this.response = response;
    return this;
  }

  @Override
  public ChatResponse ask(ChatRequest request, Subject subject) {
    return response;
  }
}
