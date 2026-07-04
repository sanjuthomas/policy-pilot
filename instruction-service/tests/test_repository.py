from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from inst.constants import INSTRUCTION_CURRENT_OUT
from inst.models.instruction import CashSettlementInstruction
from inst.repository import (
    ConcurrentModificationError,
    InstructionNotFoundError,
    InstructionRepository,
)
from inst.storage import (
    versioned_instruction_to_document,
)
from pymongo.errors import DuplicateKeyError, OperationFailure


def _current_doc(sample_instruction: CashSettlementInstruction) -> dict:
    return versioned_instruction_to_document(
        sample_instruction,
        version_number=1,
        valid_in=datetime.utcnow(),
    )


@pytest.fixture
def mock_collection() -> MagicMock:
    return MagicMock()


@pytest.fixture
def repo(mock_collection: MagicMock) -> InstructionRepository:
    with patch("inst.repository.get_database") as mock_get_db:
        mock_get_db.return_value.__getitem__ = MagicMock(return_value=mock_collection)
        yield InstructionRepository()


@pytest.mark.asyncio
async def test_insert_initial(
    repo: InstructionRepository,
    mock_collection: MagicMock,
    sample_instruction: CashSettlementInstruction,
) -> None:
    mock_collection.insert_one = AsyncMock()
    result = await repo.insert_initial(sample_instruction)
    mock_collection.insert_one.assert_awaited_once()
    assert result.instruction.instruction_id == sample_instruction.instruction_id
    assert result.version_number == 1


@pytest.mark.asyncio
async def test_append_version_success(
    repo: InstructionRepository,
    mock_collection: MagicMock,
    sample_instruction: CashSettlementInstruction,
) -> None:
    now_doc = _current_doc(sample_instruction)
    mock_collection.find_one = AsyncMock(return_value=now_doc)
    mock_collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_collection.insert_one = AsyncMock()

    result = await repo.append_version(sample_instruction)
    assert result.version_number == 2
    mock_collection.update_one.assert_awaited_once()
    mock_collection.insert_one.assert_awaited_once()
    mock_collection.delete_one.assert_not_called()


@pytest.mark.asyncio
async def test_append_version_not_found(
    repo: InstructionRepository,
    mock_collection: MagicMock,
    sample_instruction: CashSettlementInstruction,
) -> None:
    mock_collection.find_one = AsyncMock(return_value=None)
    with pytest.raises(InstructionNotFoundError):
        await repo.append_version(sample_instruction)


@pytest.mark.asyncio
async def test_append_version_concurrent_modification(
    repo: InstructionRepository,
    mock_collection: MagicMock,
    sample_instruction: CashSettlementInstruction,
) -> None:
    now_doc = _current_doc(sample_instruction)
    mock_collection.find_one = AsyncMock(return_value=now_doc)
    mock_collection.update_one = AsyncMock(return_value=MagicMock(modified_count=0))

    with pytest.raises(ConcurrentModificationError):
        await repo.append_version(sample_instruction)


@pytest.mark.asyncio
async def test_append_version_duplicate_key(
    repo: InstructionRepository,
    mock_collection: MagicMock,
    sample_instruction: CashSettlementInstruction,
) -> None:
    now_doc = _current_doc(sample_instruction)
    mock_collection.find_one = AsyncMock(return_value=now_doc)
    mock_collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_collection.insert_one = AsyncMock(side_effect=DuplicateKeyError("dup"))

    with pytest.raises(ConcurrentModificationError):
        await repo.append_version(sample_instruction)


@pytest.mark.asyncio
async def test_append_version_transient_transaction_error(
    repo: InstructionRepository,
    mock_collection: MagicMock,
    sample_instruction: CashSettlementInstruction,
) -> None:
    now_doc = _current_doc(sample_instruction)
    mock_collection.find_one = AsyncMock(return_value=now_doc)
    mock_collection.update_one = AsyncMock(
        side_effect=OperationFailure("conflict", code=112, details={"errorLabels": []})
    )

    with pytest.raises(ConcurrentModificationError):
        await repo.append_version(sample_instruction)


@pytest.mark.asyncio
async def test_get_one_requires_out(
    repo: InstructionRepository,
    sample_instruction: CashSettlementInstruction,
) -> None:
    with pytest.raises(ValueError, match="out is required"):
        await repo.get_one(sample_instruction.instruction_id, out="")


@pytest.mark.asyncio
async def test_get_one_found(
    repo: InstructionRepository,
    mock_collection: MagicMock,
    sample_instruction: CashSettlementInstruction,
) -> None:
    doc = versioned_instruction_to_document(
        sample_instruction,
        version_number=1,
        valid_in=datetime.utcnow(),
    )
    mock_collection.find_one = AsyncMock(return_value=doc)
    result = await repo.get_one(
        sample_instruction.instruction_id,
        out=INSTRUCTION_CURRENT_OUT,
    )
    assert result.instruction.instruction_id == sample_instruction.instruction_id
    args, kwargs = mock_collection.find_one.await_args
    assert args[0]["out"] == INSTRUCTION_CURRENT_OUT


@pytest.mark.asyncio
async def test_get_current_found(
    repo: InstructionRepository,
    mock_collection: MagicMock,
    sample_instruction: CashSettlementInstruction,
) -> None:
    doc = versioned_instruction_to_document(
        sample_instruction,
        version_number=1,
        valid_in=datetime.utcnow(),
    )
    mock_collection.find_one = AsyncMock(return_value=doc)
    result = await repo.get_current(sample_instruction.instruction_id)
    assert result.instruction.instruction_id == sample_instruction.instruction_id


@pytest.mark.asyncio
async def test_get_current_not_found(
    repo: InstructionRepository,
    mock_collection: MagicMock,
) -> None:
    mock_collection.find_one = AsyncMock(return_value=None)
    with pytest.raises(InstructionNotFoundError):
        await repo.get_current("missing")


@pytest.mark.asyncio
async def test_list_current(
    repo: InstructionRepository,
    mock_collection: MagicMock,
    sample_instruction: CashSettlementInstruction,
) -> None:
    doc = versioned_instruction_to_document(
        sample_instruction,
        version_number=1,
        valid_in=datetime.utcnow(),
    )

    async def _async_iter():
        yield doc

    mock_collection.find.return_value.sort.return_value.limit.return_value = _async_iter()
    results = await repo.list_current(owning_lob="FICC", status="DRAFT", limit=10)
    assert len(results) == 1
    assert results[0].instruction.owning_lob == "FICC"
    mock_collection.find.assert_called_once_with(
        {"out": INSTRUCTION_CURRENT_OUT, "owning_lob": "FICC", "status": "DRAFT"}
    )


@pytest.mark.asyncio
async def test_list_versions(
    repo: InstructionRepository,
    mock_collection: MagicMock,
    sample_instruction: CashSettlementInstruction,
) -> None:
    docs = [
        versioned_instruction_to_document(
            sample_instruction,
            version_number=version,
            valid_in=datetime.utcnow(),
        )
        for version in (1, 2)
    ]

    async def _async_iter():
        for doc in docs:
            yield doc

    mock_collection.find.return_value.sort.return_value = _async_iter()
    results = await repo.list_versions(sample_instruction.instruction_id)
    assert len(results) == 2
    assert results[0].version_number == 1
    assert results[1].version_number == 2
