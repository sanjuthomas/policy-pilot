[# th:switch="${m.variant}"]
[# th:case="'blocked'"]Payment `[(${m.paymentId})]` is not open for funding approval[# th:if="${m.blockedReason != null}"]: [(${m.blockedReason})][/][# th:if="${m.blockedReason == null}"].[/]
[/]
[# th:case="'empty'"]No other users currently satisfy APPROVE policy for payment `[(${m.paymentId})]` (you are the only eligible approver, or none remain after excluding you).
[/]
[# th:case="'found'"]Other users who can approve payment `[(${m.paymentId})]` (excluding you):

[# th:with="rows=${m.others}"][# th:insert="~{fragments/approver-table}"][/][/]
[/]
[/]
