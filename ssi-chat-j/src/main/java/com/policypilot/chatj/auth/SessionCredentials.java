package com.policypilot.chatj.auth;

public record SessionCredentials(String sessionId, String sessionToken, String userId) {}
