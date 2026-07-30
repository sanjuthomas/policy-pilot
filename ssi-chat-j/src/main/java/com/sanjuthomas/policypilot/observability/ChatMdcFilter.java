package com.sanjuthomas.policypilot.observability;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.UUID;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * Puts {@code request_id} + low-cardinality {@code http.route} on MDC for every request; clears in
 * {@code finally}.
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 10)
public class ChatMdcFilter extends OncePerRequestFilter {

  @Override
  protected void doFilterInternal(
      HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
      throws ServletException, IOException {
    String incoming = request.getHeader("X-Request-Id");
    String requestId =
        (incoming == null || incoming.isBlank()) ? UUID.randomUUID().toString() : incoming.strip();
    ChatLogContext.clearAll();
    org.slf4j.MDC.put(ChatLogContext.REQUEST_ID, requestId);
    org.slf4j.MDC.put(ChatLogContext.HTTP_ROUTE, HttpRouteTemplates.template(request.getRequestURI()));
    response.setHeader("X-Request-Id", requestId);
    try {
      filterChain.doFilter(request, response);
    } finally {
      ChatLogContext.clearAll();
    }
  }
}
