package com.sanjuthomas.policypilot.auth;

public record SessionCredentials(String sessionId, String sessionToken, String userId) {}
