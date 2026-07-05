// Neo4j graph model — instructions and security events
// Documentation only. No data is created by this file.
//
// Two ETL pipelines write to this graph:
//   1. InstructionSecurityEventPipeline  — consumes instruction_security_events topic
//   2. InstructionPipeline    — consumes instructions topic
//
// Source of truth in MongoDB:
//   ssi_cash_instructions.instructions
//   security_events.instruction-service
//
// Both topics carry full fact events — no API callbacks from the ETL.
//
// ---------------------------------------------------------------------------
// NODE LABELS
// ---------------------------------------------------------------------------
//
// (:Instruction)
//   instruction_id          unique business id (UUID)
//   owning_lob              FICC | FX | DESK_*
//   instruction_type        STANDING | SINGLE_USE
//   wire_scope              DOMESTIC | INTERNATIONAL
//   currency                ISO 4217 route currency
//
// (:InstructionVersion)
//   version_key             unique "{instruction_id}:{version_number}" (Community Edition)
//   instruction_id          + version_number also enforced as a composite unique constraint
//   version_number
//   status                  DRAFT | PENDING | STANDING | SINGLE_USE | SUSPENDED | REJECTED | USED | EXPIRED | CANCELLED
//   action                  lifecycle action that produced this version (CREATE | SUBMIT | APPROVE | ...)
//   instruction_type        STANDING | SINGLE_USE
//   wire_scope              DOMESTIC | INTERNATIONAL
//   owning_lob              FICC | FX | DESK_*
//   currency                ISO 4217 route currency
//   effective_date
//   end_date
//   is_expired              true when end_date < today (computed on every upsert)
//   creditor_name
//   creditor_account        account identification (IBAN / BBAN / proprietary)
//   creditor_scheme         IBAN | BBAN | PROPRIETARY
//   creditor_bic            creditor agent BIC / clearing code
//   debtor_name
//   debtor_account
//   debtor_bic
//   creator_user_id
//   approver_user_id
//   rejector_user_id
//   timestamp               ISO datetime of the mutation that created this version
//
// (:SecurityEvent)
//   event_id                unique UUID
//   timestamp
//   severity                INFO | LOW | MEDIUM | HIGH | ALERT | CRITICAL
//   message
//   action                  CREATE | SUBMIT | APPROVE | REJECT | VIEW | DELETE | ...
//   outcome                 success | failure
//   event_type              JSON array string (ECS-style types)
//   reason                  policy denial reason when present
//   wire_scope
//   instruction_type
//   owning_lob
//   source_application
//   source_version
//
// (:User)
//   user_id                 unique ZITADEL / seed user id
//   given_name
//   family_name
//   display_name            "FamilyName, GivenName (user_id)" — computed on upsert
//   title                   Analyst | Associate | Vice President | ...
//   lob                     profit center when applicable
//   roles                   JSON array string
//   supervisor_id
//
// (:ProfitCenter)
//   name                    unique: FICC | FX | DESK_*
//
// ---------------------------------------------------------------------------
// RELATIONSHIP TYPES
// ---------------------------------------------------------------------------
//
// ── Instruction structure ────────────────────────────────────────────────────
//
// (:Instruction)-[:HAS_VERSION]->(:InstructionVersion)
//   Logical instruction to each point-in-time version.
//
// (:Instruction)-[:CURRENT]->(:InstructionVersion)
//   Points to the highest version_number seen so far.
//   Version-aware: only advances forward — never overwritten by older events.
//
// (:InstructionVersion)-[:SUPERSEDES]->(:InstructionVersion)
// (:PaymentVersion)-[:SUPERSEDES]->(:PaymentVersion)
//   Newer version (N) links to previous version (N-1) when both exist.
//   Enables ordered history traversal and adjacent-version diff (what changed).
//   Target writer: InstructionPipeline, PaymentFactPipeline (state/fact only).
//   Alpha: InstructionSecurityEventPipeline writes InstructionVersion SUPERSEDES only.
//
// ── Instruction ownership ────────────────────────────────────────────────────
//
// (:Instruction)-[:OWNED_BY]->(:ProfitCenter)
//   Maps instruction.owning_lob to a profit center node.
//   Written by: InstructionPipeline
//
// (:InstructionVersion)-[:BELONGS_TO]->(:ProfitCenter)
//   Maps each version's owning_lob to a profit center node.
//   Written by: InstructionPipeline
//
// ── Instruction lifecycle actors ─────────────────────────────────────────────
//
// (:User)-[:CREATED]->(:InstructionVersion)
//   From instruction.created_by on the version payload.
//
// (:User)-[:SUBMITTED]->(:InstructionVersion)
//   The actor of a successful SUBMIT event.
//
// (:User)-[:APPROVED]->(:InstructionVersion)
//   From instruction.approved_by when present.
//
// (:User)-[:REJECTED]->(:InstructionVersion)
//   From instruction.rejected_by when present.
//
// Lifecycle timelines use named edges (CREATED, SUBMITTED, APPROVED, …) plus
// version properties (action, timestamp, actor ids on the version node).
// There is no generic MUTATED edge.
//
// ── Cross-instruction analytics ─────────────────────────────────────────────
//
// (:Instruction)-[:CONFLICTS_WITH]->(:Instruction)
//   Two active instructions share the same creditor_account + currency —
//   potential duplicate settlement route. Written in both directions.
//   Written by: InstructionPipeline (evaluated on every APPROVE)
//
// ── Reporting lines ─────────────────────────────────────────────────────────
//
// (:User)-[:REPORTS_TO]->(:User)
//   From actor/creator/approver/rejector supervisor_id.
//   [planned — not yet written by ETL]
//
// ── Security event graph ─────────────────────────────────────────────────────
//
// (:User)-[:ACTED_AS]->(:SecurityEvent)
//   Security event actor (subject who performed the action).
//   Written by: InstructionSecurityEventPipeline
//
// (:SecurityEvent)-[:TARGETS]->(:Instruction)
//   From security_event.resource.id.
//   Written by: InstructionSecurityEventPipeline
//
// (:SecurityEvent)-[:TARGETS_VERSION]->(:InstructionVersion)
//   When security_event.resource.version_number is set.
//   Written by: InstructionSecurityEventPipeline
//
// (:SecurityEvent)-[:INVOLVES_LOB]->(:ProfitCenter)
//   From security_event.resource.owning_lob.
//   Written by: InstructionSecurityEventPipeline

// ---------------------------------------------------------------------------
// PAYMENT NODE (append-only versioned — mirrors Instruction / InstructionVersion)
// ---------------------------------------------------------------------------
//
// (:Payment)
//   payment_id          unique business id (sequence id)
//   instruction_id      backing SSI instruction (stable on root)
//
// (:PaymentVersion)
//   version_key         unique "{payment_id}:{version_number}"
//   payment_id          parent payment id
//   version_number      monotonic lifecycle version (1 = create, increments per mutation)
//   status              DRAFT | SUBMITTED | APPROVED | REJECTED | CANCELLED
//   amount              numeric payment amount
//   currency            ISO 4217 currency code (from instruction)
//   value_date          intended settlement date (ISO string YYYY-MM-DD)
//   owning_lob          LOB from the backing instruction
//   instruction_type    STANDING | SINGLE_USE
//   creator_user_id
//   submitter_user_id
//   approver_user_id
//   rejector_user_id
//   created_at
//   updated_at
//   timestamp           mutation timestamp from Mongo CDC row
//
// (:Payment)-[:HAS_VERSION]->(:PaymentVersion)
//   All point-in-time payment versions (never deleted on new mutations).
//   Written by: PaymentFactPipeline, PaymentSecurityEventPipeline
//
// (:Payment)-[:CURRENT]->(:PaymentVersion)
//   Latest version (only advances, never regresses).
//   Written by: PaymentFactPipeline, PaymentSecurityEventPipeline
//
// (:Instruction)-[:HAS_PAYMENT]->(:Payment)
//   One instruction can have many payments (STANDING = many; SINGLE_USE = at most one).
//   Written by: PaymentFactPipeline
//
// (:User)-[:CREATED_PAYMENT]->(:PaymentVersion)
//   The PAYMENT_CREATOR who created the payment request.
//   Written by: PaymentFactPipeline
//
// (:User)-[:SUBMITTED_PAYMENT]->(:PaymentVersion)
//   The user who submitted the payment for approval.
//   Written by: PaymentFactPipeline
//
// (:User)-[:APPROVED_PAYMENT]->(:PaymentVersion)
//   The FUNDING_APPROVER who approved the payment.
//   Written by: PaymentFactPipeline
//
// (:User)-[:REJECTED_PAYMENT]->(:PaymentVersion)
//   The FUNDING_APPROVER who rejected the payment.
//   Written by: PaymentFactPipeline
//
// (:SecurityEvent)-[:TARGETS_PAYMENT]->(:Payment)
//   Payment security events link to the payment root.
//   Written by: PaymentSecurityEventPipeline
//
// (:SecurityEvent)-[:TARGETS_PAYMENT_VERSION]->(:PaymentVersion)
//   When resource.version_number is set on the security event.
//   Written by: PaymentSecurityEventPipeline
