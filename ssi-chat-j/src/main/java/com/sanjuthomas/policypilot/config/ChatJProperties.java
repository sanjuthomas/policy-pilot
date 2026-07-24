package com.sanjuthomas.policypilot.config;

import java.util.List;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

@ConfigurationProperties(prefix = "chatj")
public record ChatJProperties(
    String paymentServiceUrl,
    String instructionServiceUrl,
    String authorizationServiceUrl,
    @DefaultValue("http://localhost:8090") String indexerUrl,
    String neo4jUri,
    String neo4jUser,
    String neo4jPassword,
    @DefaultValue("multimodal_embedding") String multimodalVectorIndex,
    @DefaultValue("8") int retrievalLimit,
    String zitadelUrl,
    String zitadelInternalUrl,
    String zitadelHostHeader,
    String zitadelServicePat,
    String zitadelServicePatFile,
    String oidcIssuerUrl,
    String oidcInternalUrl,
    String oidcAudience,
    String emailDomain,
    String serviceUserId,
    String serviceUserPassword,
    List<String> chatRoles) {}
