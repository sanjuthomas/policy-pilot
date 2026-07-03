FROM confluentinc/cp-kafka-connect:7.7.1

USER root
RUN confluent-hub install --no-prompt mongodb/kafka-connect-mongodb:1.16.0
USER appuser
