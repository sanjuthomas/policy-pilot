[# th:switch="${m.variant}"]
[# th:case="'need_lob'"]Include a desk LOB when asking who covers it, for example: “Who covers LOB FICC?” or “Which users cover FX?”
[/]
[# th:case="'empty'"]No users in the directory list **[(${m.lob})]** in their covering LOBs.
[/]
[# th:case="'ok'"]Users who **cover LOB [(${m.lob})]** (directory `covering_lobs` includes [(${m.lob})]) — [(${m.matchCount})] user(s):

[# th:each="u : ${m.users}"]
- **[(${u.displayName})]** (`[(${u.userId})]`) — [(${u.title})]
  - Roles: [(${u.roles})]
  - Covering LOBs: [(${u.coveringLobs})]
[/]
[/]
[/]
