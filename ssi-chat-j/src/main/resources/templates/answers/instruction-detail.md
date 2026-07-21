### Instruction `[(${m.instructionId})]`

| Field | Value |
|-------|-------|
| Instruction id | `[(${m.instructionId})]` |
| Status | **[(${m.status})]** |
| Type | [(${m.instructionType})] |
| Owning LOB | **[(${m.owningLob})]** |
| Currency | [(${m.currency})] |
| Wire scope | [(${m.wireScope})] |
| Creditor | [(${m.creditor})] |
| Effective | [(${m.effectiveDate})] |
| End | [(${m.endDate})] |
| Current version | [(${m.versionNumber})] |
| Creator | [(${m.creator})] |
| Approver | [(${m.approver})] |
[# th:if="${m.createdAt != null}"]

Created at: [(${m.createdAt})][/][# th:if="${m.approvedAt != null}"]
Approved at: [(${m.approvedAt})][/]
