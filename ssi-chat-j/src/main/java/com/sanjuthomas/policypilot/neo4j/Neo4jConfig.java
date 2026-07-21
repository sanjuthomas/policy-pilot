package com.sanjuthomas.policypilot.neo4j;

import com.sanjuthomas.policypilot.config.ChatJProperties;
import org.neo4j.driver.AuthTokens;
import org.neo4j.driver.Driver;
import org.neo4j.driver.GraphDatabase;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class Neo4jConfig {

  @Bean(destroyMethod = "close")
  Driver neo4jDriver(ChatJProperties properties) {
    return GraphDatabase.driver(
        properties.neo4jUri(),
        AuthTokens.basic(properties.neo4jUser(), properties.neo4jPassword()));
  }
}
