from uuid import UUID
from typing import Any, List, Optional, Tuple

import asyncpg

from app.domain.entities import AssistantMessage
from app.domain.types import AssistantAnswerStatus
from app.infra.database.postgres import PostgresPool
from app.application.interfaces import IAssistantMessageRepository
from app.domain.exceptions.transaction_exceptions import UserNotFoundError
from app.application.dto import (
    ConversationTurnDTO,
    ListAssistantMessagesRequestDTO,
    CreateAssistantMessageRequestDTO
)


class AssistantMessageRepository(IAssistantMessageRepository):

    def __init__(self, pool: PostgresPool) -> None:
        self._pool = pool

    async def create(
            self,
            create_assistant_message_request: CreateAssistantMessageRequestDTO
    ) -> AssistantMessage:
        try:
            async with self._pool.tenant_transaction(create_assistant_message_request.partner_id) as connection:
                record = await connection.fetchrow(
                    """
                        INSERT INTO assistant_messages (
                            partner_id,
                            user_id,
                            conversation_id,
                            question,
                            answer,
                            status,
                            model,
                            context_source_ids
                        )
                        VALUES (
                            $1,
                            $2,
                            $3,
                            $4,
                            $5,
                            $6,
                            $7,
                            $8
                        )
                        RETURNING
                            message_id,
                            partner_id,
                            user_id,
                            conversation_id,
                            question,
                            answer,
                            status,
                            model,
                            context_source_ids,
                            created_at
                    """,
                    create_assistant_message_request.partner_id,
                    create_assistant_message_request.user_id,
                    create_assistant_message_request.conversation_id,
                    create_assistant_message_request.question,
                    create_assistant_message_request.answer,
                    create_assistant_message_request.status.value,
                    create_assistant_message_request.model,
                    create_assistant_message_request.context_source_ids
                )
        except asyncpg.ForeignKeyViolationError as exc:
            raise UserNotFoundError() from exc

        return self._to_entity(record)

    async def list_recent_turns(
            self,
            limit: int,
            user_id: UUID,
            partner_id: UUID,
            conversation_id: UUID
    ) -> List[ConversationTurnDTO]:
        if limit <= 0:
            return []

        async with self._pool.tenant_transaction(partner_id) as connection:
            records = await connection.fetch(
                """
                    SELECT
                        question,
                        answer
                    FROM (
                        SELECT
                            question,
                            answer,
                            created_at,
                            message_id
                        FROM assistant_messages
                        WHERE partner_id = $1
                            AND user_id = $2
                            AND conversation_id = $3
                            AND status = 'ANSWERED'
                        ORDER BY created_at DESC, message_id DESC
                        LIMIT $4
                    ) AS recent
                    ORDER BY recent.created_at, recent.message_id
                """,
                partner_id,
                user_id,
                conversation_id,
                limit
            )

        return [
            ConversationTurnDTO(question=record.get("question"), answer=record.get("answer"))
            for record in records
        ]

    async def list_by_filter(
            self,
            list_assistant_messages_request: ListAssistantMessagesRequestDTO
    ) -> Tuple[List[AssistantMessage], int]:
        conditions = [
            "partner_id = $1",
            "user_id = $2"
        ]

        arguments: List[Any] = [
            list_assistant_messages_request.partner_id,
            list_assistant_messages_request.user_id
        ]

        if list_assistant_messages_request.conversation_id is not None:
            arguments.append(list_assistant_messages_request.conversation_id)
            conditions.append(f"conversation_id = ${len(arguments)}")

        if list_assistant_messages_request.status is not None:
            arguments.append(list_assistant_messages_request.status.value)
            conditions.append(f"status = ${len(arguments)}")

        arguments.append(list_assistant_messages_request.page_size)
        limit_placeholder = f"${len(arguments)}"

        arguments.append(list_assistant_messages_request.offset)
        offset_placeholder = f"${len(arguments)}"

        async with self._pool.tenant_transaction(list_assistant_messages_request.partner_id) as connection:
            records = await connection.fetch(
                f"""
                    SELECT
                        message_id,
                        partner_id,
                        user_id,
                        conversation_id,
                        question,
                        answer,
                        status,
                        model,
                        context_source_ids,
                        created_at,
                        count(*) OVER () AS total_count
                    FROM assistant_messages
                    WHERE {" AND ".join(conditions)}
                    ORDER BY created_at DESC, message_id DESC
                    LIMIT {limit_placeholder}
                    OFFSET {offset_placeholder}
                """,
                *arguments
            )

        if not records:
            return [], 0

        total = int(records[0].get("total_count"))

        return [self._to_entity(record) for record in records], total

    @staticmethod
    def _to_entity(record: asyncpg.Record) -> AssistantMessage:
        source_ids: Optional[List[Any]] = record.get("context_source_ids")

        return AssistantMessage(
            model=record.get("model"),
            answer=record.get("answer"),
            question=record.get("question"),
            created_at=record.get("created_at"),
            user_id=UUID(str(record.get("user_id"))),
            partner_id=UUID(str(record.get("partner_id"))),
            message_id=UUID(str(record.get("message_id"))),
            status=AssistantAnswerStatus(record.get("status")),
            conversation_id=UUID(str(record.get("conversation_id"))),
            context_source_ids=[UUID(str(source_id)) for source_id in source_ids or []]
        )
