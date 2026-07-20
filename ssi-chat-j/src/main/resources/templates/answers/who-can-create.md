[# th:switch="${m.variant}"]
[# th:case="'payment_empty'"][# th:if="${m.lobLabel != null}"]Users who can **create** (draft) payments for LOB **[(${m.lobLabel})]** — role `PAYMENT_CREATOR`, group `MIDDLE_OFFICE`, covering LOBs include [(${m.lobLabel})]:

No middle-office payment creators cover LOB [(${m.lobLabel})].[/][# th:if="${m.lobLabel == null}"]Users who can **create** (draft) payments — role `PAYMENT_CREATOR` and group `MIDDLE_OFFICE` (with covering LOBs / amount clubs):

No middle-office payment creators were found in the directory.[/]
[/]
[# th:case="'payment_ok'"][# th:if="${m.lobLabel != null}"]Users who can **create** (draft) payments for LOB **[(${m.lobLabel})]** — role `PAYMENT_CREATOR`, group `MIDDLE_OFFICE`, covering LOBs include [(${m.lobLabel})]:[/][# th:if="${m.lobLabel == null}"]Users who can **create** (draft) payments — role `PAYMENT_CREATOR` and group `MIDDLE_OFFICE` (with covering LOBs / amount clubs):[/]

[# th:each="c : ${m.creators}"]
- **[(${c.displayName})]** (`[(${c.userId})]`) — [(${c.title})]; covering [ [(${c.covering})] ]; clubs [ [(${c.clubs})] ]; groups [ [(${c.groups})] ][# th:if="${c.you}"] ← you[/]
[/]

Front-office users with only desk lob (for example fo-fx-101) **submit** payment drafts; they do not create them. Payment CREATE still requires a usable instruction and an amount within the creator's club at mutation time.
[/]
[# th:case="'instruction_empty'"]Users who can **create** (draft) instructions — role `INSTRUCTION_CREATOR`, group `MIDDLE_OFFICE`, with an eligible creator title:[# th:if="${m.lobLabel != null}"]

For owning LOB **[(${m.lobLabel})]**, any of these creators may draft when the account owning LOB matches and other OPA checks pass (profit center, duration). Instruction creators are not scoped by payment `covering_lobs`.[/]

No middle-office instruction creators were found.
[/]
[# th:case="'instruction_ok'"]Users who can **create** (draft) instructions — role `INSTRUCTION_CREATOR`, group `MIDDLE_OFFICE`, with an eligible creator title:[# th:if="${m.lobLabel != null}"]

For owning LOB **[(${m.lobLabel})]**, any of these creators may draft when the account owning LOB matches and other OPA checks pass (profit center, duration). Instruction creators are not scoped by payment `covering_lobs`.[/]

[# th:each="c : ${m.creators}"]
- **[(${c.displayName})]** (`[(${c.userId})]`) — [(${c.title})]; supervisor `[(${c.supervisor})]`[# th:if="${c.you}"] ← you[/]
[/]

Do not confuse with **payment** creators (`PAYMENT_CREATOR` + covering LOBs). Instruction create uses `INSTRUCTION_CREATOR` (e.g. mo-100, mo-101).
[/]
[/]
