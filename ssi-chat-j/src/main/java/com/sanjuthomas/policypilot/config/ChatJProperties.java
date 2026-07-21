package com.sanjuthomas.policypilot.config;

import java.util.List;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "chatj")
public record ChatJProperties(
    String paymentServiceUrl,
    String instructionServiceUrl,
    String authorizationServiceUrl,
    String cypherBuilderServiceUrl,
    String neo4jUri,
    String neo4jUser,
    String neo4jPassword,
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
