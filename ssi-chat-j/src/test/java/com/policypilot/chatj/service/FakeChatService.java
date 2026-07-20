package com.policypilot.chatj.service;

import com.policypilot.chatj.api.ApiModels.ChatRequest;
import com.policypilot.chatj.api.ApiModels.ChatResponse;
import com.policypilot.chatj.auth.Subject;

public class FakeChatService extends ChatService {

  private ChatResponse response = ChatResponse.of("default", null);

  public FakeChatService() {
    super(null, null, null, null, null);
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
