[# th:if="${m.missing}"]No [(${m.entityNoun})] with that ID was found in the graph.[/][# th:if="${!m.missing}"][(${m.displayNoun})]: [(${m.entityId})]
Creator: [(${m.creatorDisplay})]
Approver: [(${m.approverDisplay})][# th:if="${m.approvedAt != null and !m.approvedAt.isEmpty()}"]
Approved at: [(${m.approvedAt})][/][/]
