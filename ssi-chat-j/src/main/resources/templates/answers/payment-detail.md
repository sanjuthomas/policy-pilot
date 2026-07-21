### Payment `[(${m.paymentId})]`

| Field | Value |
|-------|-------|
| Payment id | `[(${m.paymentId})]` |
| Instruction | `[(${m.instructionId})]` |
| Status | **[(${m.status})]** |
| Amount | **[(${m.amount})]** |
| Value date | [(${m.valueDate})] |
| Owning LOB | **[(${m.owningLob})]** |
| Creator | [(${m.creator})] |
| Approver | [(${m.approver})] |
[# th:if="${m.createdAt != null}"]

Created at: [(${m.createdAt})][/][# th:if="${m.approvedAt != null}"]
Approved at: [(${m.approvedAt})][/]
