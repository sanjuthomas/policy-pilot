// Constraints — one node per business key
CREATE CONSTRAINT instruction_id_unique IF NOT EXISTS
FOR (i:Instruction) REQUIRE i.instruction_id IS UNIQUE;

CREATE CONSTRAINT instruction_version_key_unique IF NOT EXISTS
FOR (v:InstructionVersion) REQUIRE v.version_key IS UNIQUE;

CREATE CONSTRAINT instruction_version_id_num_unique IF NOT EXISTS
FOR (v:InstructionVersion) REQUIRE (v.instruction_id, v.version_number) IS UNIQUE;

CREATE CONSTRAINT security_event_id_unique IF NOT EXISTS
FOR (e:SecurityEvent) REQUIRE e.event_id IS UNIQUE;

CREATE CONSTRAINT user_id_unique IF NOT EXISTS
FOR (u:User) REQUIRE u.user_id IS UNIQUE;

CREATE CONSTRAINT profit_center_lob_unique IF NOT EXISTS
FOR (p:ProfitCenter) REQUIRE p.lob IS UNIQUE;

// Indexes — common filter and traversal paths
CREATE INDEX instruction_version_status IF NOT EXISTS
FOR (v:InstructionVersion) ON (v.status);

CREATE INDEX instruction_version_owning_lob IF NOT EXISTS
FOR (v:InstructionVersion) ON (v.owning_lob);

CREATE INDEX security_event_timestamp IF NOT EXISTS
FOR (e:SecurityEvent) ON (e.timestamp);

CREATE INDEX security_event_severity IF NOT EXISTS
FOR (e:SecurityEvent) ON (e.severity);

CREATE INDEX security_event_action IF NOT EXISTS
FOR (e:SecurityEvent) ON (e.action);

CREATE INDEX user_lob IF NOT EXISTS
FOR (u:User) ON (u.lob);

CREATE INDEX instruction_version_creditor_account IF NOT EXISTS
FOR (v:InstructionVersion) ON (v.creditor_account_id);

CREATE INDEX instruction_version_debtor_account IF NOT EXISTS
FOR (v:InstructionVersion) ON (v.debtor_account_id);

CREATE INDEX instruction_version_currency IF NOT EXISTS
FOR (v:InstructionVersion) ON (v.currency);

CREATE INDEX instruction_version_is_expired IF NOT EXISTS
FOR (v:InstructionVersion) ON (v.is_expired);

CREATE INDEX instruction_version_effective_date IF NOT EXISTS
FOR (v:InstructionVersion) ON (v.effective_date);

CREATE INDEX instruction_version_end_date IF NOT EXISTS
FOR (v:InstructionVersion) ON (v.end_date);

// Payment constraints and indexes (append-only versioned model — mirrors Instruction)
CREATE CONSTRAINT payment_id_unique IF NOT EXISTS
FOR (p:Payment) REQUIRE p.payment_id IS UNIQUE;

CREATE CONSTRAINT payment_version_key_unique IF NOT EXISTS
FOR (v:PaymentVersion) REQUIRE v.version_key IS UNIQUE;

CREATE CONSTRAINT payment_version_id_num_unique IF NOT EXISTS
FOR (v:PaymentVersion) REQUIRE (v.payment_id, v.version_number) IS UNIQUE;

CREATE INDEX payment_instruction_id IF NOT EXISTS
FOR (p:Payment) ON (p.instruction_id);

CREATE INDEX payment_version_status IF NOT EXISTS
FOR (v:PaymentVersion) ON (v.status);

CREATE INDEX payment_version_owning_lob IF NOT EXISTS
FOR (v:PaymentVersion) ON (v.owning_lob);

CREATE INDEX payment_version_value_date IF NOT EXISTS
FOR (v:PaymentVersion) ON (v.value_date);

CREATE INDEX payment_version_created_at IF NOT EXISTS
FOR (v:PaymentVersion) ON (v.created_at);

CREATE INDEX payment_security_event_id IF NOT EXISTS
FOR (e:SecurityEvent) ON (e.payment_id);

// Multimodal store — unified vector + fulltext search in Neo4j
CREATE CONSTRAINT multimodal_document_id_unique IF NOT EXISTS
FOR (d:MultimodalDocument) REQUIRE d.document_id IS UNIQUE;

CREATE INDEX multimodal_source IF NOT EXISTS
FOR (d:MultimodalDocument) ON (d.source);

CREATE INDEX multimodal_event_id IF NOT EXISTS
FOR (d:MultimodalDocument) ON (d.event_id);

CREATE INDEX multimodal_instruction_id IF NOT EXISTS
FOR (d:MultimodalDocument) ON (d.instruction_id);

CREATE INDEX multimodal_payment_id IF NOT EXISTS
FOR (d:MultimodalDocument) ON (d.payment_id);

CREATE INDEX instruction_current_status IF NOT EXISTS
FOR (i:Instruction) ON (i.current_status);

CREATE INDEX instruction_current_used_by IF NOT EXISTS
FOR (i:Instruction) ON (i.current_used_by);

CREATE INDEX instruction_version_valid_in IF NOT EXISTS
FOR (v:InstructionVersion) ON (v.valid_in);

CREATE INDEX instruction_version_used_by IF NOT EXISTS
FOR (v:InstructionVersion) ON (v.used_by);

CREATE INDEX payment_current_status IF NOT EXISTS
FOR (p:Payment) ON (p.current_status);

CREATE INDEX payment_version_valid_in IF NOT EXISTS
FOR (v:PaymentVersion) ON (v.valid_in);

CREATE FULLTEXT INDEX multimodal_search_text IF NOT EXISTS
FOR (d:MultimodalDocument) ON EACH [d.search_text];
