Permissions for **[(${m.displayName})]** (`[(${m.userId})]`), derived from your signed-in identity (roles, groups, covering LOBs, amount clubs):

- **Roles:** [(${m.roles})]
- **Groups:** [(${m.groups})]
- **Amount clubs:** [(${m.amountClubs})]
- **Covering LOBs:** [(${m.coveringLobs})]
- **Desk LOB:** [(${m.deskLob})]

**Derived capabilities:**
[# th:each="line : ${m.capabilities}"]
[(${line})]
[/]

Live allow/deny on a specific payment still goes through OPA (four-eyes, reporting line, amount ceiling, instruction status).
