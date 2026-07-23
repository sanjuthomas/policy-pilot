[# th:if="${#lists.isEmpty(m.rows)}"][(${m.emptyMessage})][/][# th:if="${!#lists.isEmpty(m.rows)}"][# th:insert="~{fragments/instruction-inventory-table}"][/][/]
