from __future__ import annotations

from authz.models import PersonCapability, PersonPermissionSummary, UserDirectoryRow


def filter_directory_rows(rows: list[UserDirectoryRow], query: str) -> list[UserDirectoryRow]:
    needle = query.strip().lower()
    if not needle:
        return []

    variants = {needle}
    if "," in needle:
        family, _, given = needle.partition(",")
        family = family.strip()
        given = given.strip()
        if family and given:
            variants.add(f"{given} {family}")
            variants.add(f"{family} {given}")
    else:
        parts = needle.split()
        if len(parts) >= 2:
            variants.add(f"{parts[-1]}, {' '.join(parts[:-1])}")
            variants.add(f"{parts[0]}, {' '.join(parts[1:])}")

    matches: list[UserDirectoryRow] = []
    for row in rows:
        haystacks = {
            row.user_id.lower(),
            row.login_name.lower(),
            row.display_name.lower(),
            f"{row.given_name} {row.family_name}".lower(),
            f"{row.family_name} {row.given_name}".lower(),
            f"{row.family_name}, {row.given_name}".lower(),
        }
        if any(variant in haystack or haystack in variant for variant in variants for haystack in haystacks):
            matches.append(row)
            continue
        # Partial family/given match for single-token queries.
        if " " not in needle and "," not in needle:
            if needle in row.family_name.lower() or needle in row.given_name.lower():
                matches.append(row)
    return matches


def build_person_capabilities(row: UserDirectoryRow) -> list[PersonCapability]:
    capabilities: list[PersonCapability] = []
    roles = set(row.roles)
    groups = set(row.groups)
    clubs = ", ".join(row.amount_clubs) if row.amount_clubs else "no amount-limit club"
    covering = (
        ", ".join(row.covering_lobs) if row.covering_lobs else "no covering LOBs"
    )
    desk = row.lob or "no desk LOB"

    if "FUNDING_APPROVER" in roles and "MIDDLE_OFFICE" in groups:
        capabilities.append(
            PersonCapability(
                kind="funding_approve",
                description=(
                    f"Approve/reject payments for covering LOBs ({covering}) within "
                    f"{clubs}, subject to four-eyes and reporting-line checks"
                ),
            )
        )
    if "PAYMENT_CREATOR" in roles and "MIDDLE_OFFICE" in groups:
        capabilities.append(
            PersonCapability(
                kind="payment_create",
                description=(
                    f"Create/update/cancel draft payments for covering LOBs ({covering}) "
                    f"within {clubs}"
                ),
            )
        )
    if "PAYMENT_CREATOR" in roles and row.lob:
        capabilities.append(
            PersonCapability(
                kind="payment_submit",
                description=f"Submit payments for desk LOB {desk}",
            )
        )
    if "INSTRUCTION_CREATOR" in roles and "MIDDLE_OFFICE" in groups:
        capabilities.append(
            PersonCapability(
                kind="instruction_create",
                description=(
                    "Create/update/submit/cancel instructions as middle-office creator "
                    f"(title {row.title})"
                ),
            )
        )
    if "INSTRUCTION_APPROVER" in roles and row.lob:
        capabilities.append(
            PersonCapability(
                kind="instruction_approve",
                description=(
                    f"Approve/reject instructions for desk LOB {desk} per the title "
                    f"approval matrix (title {row.title})"
                ),
            )
        )
    if "COMPLIANCE_ANALYST" in roles:
        capabilities.append(
            PersonCapability(
                kind="compliance",
                description="Query live policy directory, summaries, and eligible approvers",
            )
        )
    if "PLATFORM_ADMIN" in roles:
        capabilities.append(
            PersonCapability(
                kind="platform_admin",
                description="Administer the platform user directory",
            )
        )
    return capabilities


def build_person_narrative(row: UserDirectoryRow, capabilities: list[PersonCapability]) -> str:
    covering = ", ".join(row.covering_lobs) if row.covering_lobs else "no covering LOBs"
    clubs = ", ".join(row.amount_clubs) if row.amount_clubs else "no amount-limit club"
    roles = ", ".join(row.roles) if row.roles else "no roles"
    groups = ", ".join(row.groups) if row.groups else "no groups"

    if not capabilities:
        return (
            f"{row.display_name} (`{row.user_id}`) holds roles [{roles}] and groups "
            f"[{groups}], but no payment/instruction approval capabilities were derived."
        )

    return (
        f"{row.display_name} (`{row.user_id}`) is a {row.title} with roles [{roles}], "
        f"groups [{groups}], amount clubs [{clubs}], and covering LOBs [{covering}]."
    )


def build_person_permission_summary(row: UserDirectoryRow) -> PersonPermissionSummary:
    capabilities = build_person_capabilities(row)
    return PersonPermissionSummary(
        user_id=row.user_id,
        display_name=row.display_name,
        title=row.title,
        lob=row.lob,
        roles=list(row.roles),
        groups=list(row.groups),
        amount_clubs=list(row.amount_clubs),
        covering_lobs=list(row.covering_lobs),
        capabilities=capabilities,
        narrative=build_person_narrative(row, capabilities),
    )
