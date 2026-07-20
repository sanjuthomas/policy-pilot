# syntax=docker/dockerfile:1

FROM maven:3.9.9-eclipse-temurin-21 AS build
WORKDIR /build

# Python static assets + ZITADEL seed (copied at Maven generate-resources)
COPY ssi-chat/src/chat_application/static /build/ssi-chat/src/chat_application/static
COPY zitadel-seed/users.yaml /build/zitadel-seed/users.yaml
COPY ssi-chat-j/pom.xml /build/ssi-chat-j/pom.xml
COPY ssi-chat-j/src /build/ssi-chat-j/src

WORKDIR /build/ssi-chat-j
RUN mvn -q -DskipTests package

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /build/ssi-chat-j/target/ssi-chat-j-*.jar /app/app.jar
EXPOSE 8096
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
