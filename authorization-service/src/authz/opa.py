from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from authz.config import settings
from authz.models import PaymentRecord, Subject


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    allow_basis: list[str]
    violations: list[str]
    is_alert: bool


class OpaClient:
    _PAYMENT_PACKAGE = "payment/lifecycle"
    _PAYMENT_ACTION = "APPROVE"
    _INSTRUCTION_PACKAGE = "instruction/lifecycle"
    _INSTRUCTION_ACTION = "APPROVE"

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.opa_url).rstrip("/")

    async def _post_data(self, path: str, payload: dict[str, Any]) -> Any:
        url = f"{self.base_url}/v1/data/{path}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            body: dict[str, Any] = response.json()
        return body.get("result")

    async def _get_data(self, path: str) -> Any:
        url = f"{self.base_url}/v1/data/{path}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            body: dict[str, Any] = response.json()
        return body.get("result")

    async def list_policy_ids(self) -> list[str]:
        url = f"{self.base_url}/v1/policies"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            body: dict[str, Any] = response.json()

        result = body.get("result", [])
        if not isinstance(result, list):
            return []
        return [
            str(item["id"])
            for item in result
            if isinstance(item, dict) and item.get("id")
        ]

    async def policy_health(
        self,
        *,
        minimum_policies: int = 15,
    ) -> dict[str, Any]:
        try:
            policy_ids = await self.list_policy_ids()
            count = len(policy_ids)
            if count < minimum_policies:
                return {
                    "ok": False,
                    "policy_count": count,
                    "detail": f"expected at least {minimum_policies} policies",
                }

            allowed = bool(
                await self._post_data(
                    "instruction/lifecycle/allow",
                    {
                        "input": {
                            "action": "CREATE",
                            "subject": {
                                "user_id": "mo-100",
                                "title": "Analyst",
                                "roles": ["INSTRUCTION_CREATOR"],
                                "groups": ["MIDDLE_OFFICE"],
                            },
                            "instruction": {
                                "status": "DRAFT",
                                "type": "SINGLE_USE",
                                "owning_lob": "FICC",
                                "effective_date": "2026-07-04T00:00:00Z",
                                "end_date": "2027-07-04T00:00:00Z",
                                "created_by": {
                                    "user_id": "mo-100",
                                    "title": "Analyst",
                                },
                            },
                            "account": {"owning_lob": "FICC"},
                        }
                    },
                )
            )
            if not allowed:
                return {
                    "ok": False,
                    "policy_count": count,
                    "detail": "instruction CREATE smoke evaluation denied",
                }

            return {"ok": True, "policy_count": count, "detail": "policies loaded"}
        except Exception as exc:
            return {"ok": False, "policy_count": 0, "detail": str(exc)}

    @staticmethod
    def _as_string_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value]
        return []

    @staticmethod
    def _violation_codes(value: Any) -> list[str]:
        if not isinstance(value, dict):
            return []
        return sorted(key for key, enabled in value.items() if enabled)

    async def _evaluate(
        self,
        package: str,
        payload: dict[str, Any],
    ) -> PolicyDecision:
        allowed = bool(await self._post_data(f"{package}/allow", payload))
        if allowed:
            basis = self._as_string_list(
                await self._post_data(f"{package}/allow_basis", payload)
            )
            return PolicyDecision(
                allowed=True,
                allow_basis=basis,
                violations=[],
                is_alert=False,
            )

        violations = self._violation_codes(
            await self._post_data(f"{package}/violations", payload)
        )
        is_alert = bool(await self._post_data(f"{package}/is_alert", payload))
        return PolicyDecision(
            allowed=False,
            allow_basis=[],
            violations=violations,
            is_alert=is_alert,
        )

    async def evaluate_instruction(
        self,
        *,
        action: str,
        subject: Subject,
        instruction: dict[str, Any],
        account: dict[str, Any],
    ) -> PolicyDecision:
        payload = {
            "input": {
                "action": action,
                "subject": subject.to_opa_subject(),
                "instruction": instruction,
                "account": account,
            }
        }
        return await self._evaluate(self._INSTRUCTION_PACKAGE, payload)

    async def evaluate_payment(
        self,
        *,
        action: str,
        subject: Subject,
        payment: dict[str, Any],
        instruction_end_date: str = "",
        instruction_status: str = "",
    ) -> PolicyDecision:
        payment_input = dict(payment)
        if instruction_end_date:
            payment_input["instruction_end_date"] = instruction_end_date
        if instruction_status:
            payment_input["instruction_status"] = instruction_status
        payload = {
            "input": {
                "action": action,
                "subject": subject.to_opa_subject(),
                "payment": payment_input,
            }
        }
        return await self._evaluate(self._PAYMENT_PACKAGE, payload)

    def _build_payment_payload(
        self,
        subject: Subject,
        payment: PaymentRecord,
        *,
        instruction_end_date: str,
        instruction_status: str,
    ) -> dict[str, Any]:
        return {
            "input": {
                "action": self._PAYMENT_ACTION,
                "subject": subject.to_opa_subject(),
                "payment": payment.to_opa_payment(
                    instruction_end_date=instruction_end_date,
                    instruction_status=instruction_status,
                ),
            }
        }

    def _build_instruction_payload(
        self,
        subject: Subject,
        *,
        opa_instruction: dict[str, Any],
        opa_account: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "input": {
                "action": self._INSTRUCTION_ACTION,
                "subject": subject.to_opa_subject(),
                "instruction": opa_instruction,
                "account": opa_account,
            }
        }

    async def can_approve_payment(
        self,
        subject: Subject,
        payment: PaymentRecord,
        *,
        instruction_end_date: str,
        instruction_status: str,
    ) -> tuple[bool, list[str]]:
        payload = self._build_payment_payload(
            subject,
            payment,
            instruction_end_date=instruction_end_date,
            instruction_status=instruction_status,
        )
        allowed = bool(await self._post_data(f"{self._PAYMENT_PACKAGE}/allow", payload))
        if not allowed:
            return False, []
        basis = self._as_string_list(
            await self._post_data(f"{self._PAYMENT_PACKAGE}/allow_basis", payload)
        )
        return True, basis

    async def can_submit_payment(
        self,
        subject: Subject,
        payment: PaymentRecord,
        *,
        instruction_end_date: str,
        instruction_status: str,
    ) -> tuple[bool, list[str]]:
        payload = {
            "input": {
                "action": "SUBMIT",
                "subject": subject.to_opa_subject(),
                "payment": payment.to_opa_payment(
                    instruction_end_date=instruction_end_date,
                    instruction_status=instruction_status,
                ),
            }
        }
        allowed = bool(await self._post_data(f"{self._PAYMENT_PACKAGE}/allow", payload))
        if not allowed:
            return False, []
        basis = self._as_string_list(
            await self._post_data(f"{self._PAYMENT_PACKAGE}/allow_basis", payload)
        )
        return True, basis

    async def can_approve_instruction(
        self,
        subject: Subject,
        *,
        opa_instruction: dict[str, Any],
        opa_account: dict[str, Any],
    ) -> tuple[bool, list[str]]:
        payload = self._build_instruction_payload(
            subject,
            opa_instruction=opa_instruction,
            opa_account=opa_account,
        )
        allowed = bool(await self._post_data(f"{self._INSTRUCTION_PACKAGE}/allow", payload))
        if not allowed:
            return False, []
        basis = self._as_string_list(
            await self._post_data(f"{self._INSTRUCTION_PACKAGE}/allow_basis", payload)
        )
        return True, basis

    async def fetch_policy_summary(self, domain: str) -> dict[str, Any]:
        normalized = domain.strip().lower()
        if normalized == "payment":
            package = self._PAYMENT_PACKAGE
        elif normalized == "instruction":
            package = self._INSTRUCTION_PACKAGE
        else:
            raise ValueError(f"unsupported policy domain: {domain}")

        result = await self._get_data(f"{package}/policy_summary")
        if not isinstance(result, dict):
            raise RuntimeError(f"OPA returned empty policy_summary for {normalized}")
        return result

    async def fetch_payment_amount_limits(self) -> dict[str, Any]:
        """Return absolute + club ceilings from OPA (no subject input)."""
        result = await self._get_data(f"{self._PAYMENT_PACKAGE}/amount_limits_catalog")
        if not isinstance(result, dict):
            raise RuntimeError("OPA returned empty amount_limits_catalog")
        return result
