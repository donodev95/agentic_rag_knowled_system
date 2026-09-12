"""Transactional conversation orchestration."""

from collections.abc import AsyncIterator
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.checkpoints import AgentCheckpointer
from backend.app.agents.providers import create_answer_provider
from backend.app.agents.types import AgentStreamEvent
from backend.app.agents.workflow import AgentState, run_agent, stream_agent
from backend.app.core.config import Settings
from backend.app.ingestion.embeddings import create_embedding_provider
from backend.app.models.message import Message, MessageRole
from backend.app.repositories.messages import create_message, list_messages


async def answer_question(
    session: AsyncSession,
    *,
    owner_id: UUID,
    thread_id: UUID,
    question: str,
    settings: Settings,
    checkpointer: AgentCheckpointer | None = None,
) -> tuple[Message, AgentState]:
    """
    Persist a user turn, run the graph, and persist its validated response.
    1. load previous history
    2. save new user message
    3. run agent
    4. save assistant message
    5. return assistant + final agent state
    """
    history = list(await list_messages(session, owner_id, thread_id)) 
    # Load the previous conversation first before creating a new messages. This ensures no duplicated messages are created in the history retrieved by the agent.
    await create_message(
        session,
        thread_id=thread_id,
        owner_id=owner_id,
        role=MessageRole.USER, # persist user's message in DB
        content=question,
    )
    # Run_Agent creates the agent state. 
    state = await run_agent(
        session=session,
        owner_id=owner_id,
        thread_id=thread_id,
        query=question,
        settings=settings,
        embedding_provider=create_embedding_provider(settings),
        answer_provider=create_answer_provider(settings),
        history=history,
        checkpointer=checkpointer,
    )
    assistant = await create_message(
        session,
        thread_id=thread_id,
        owner_id=owner_id,
        role=MessageRole.ASSISTANT, # Persist assistant's message in DB
        content=state["answer"],
        sources=state["sources"],
    )
    return assistant, state


async def stream_answer_question(
    session: AsyncSession,
    *,
    owner_id: UUID,
    thread_id: UUID,
    question: str,
    settings: Settings,
    checkpointer: AgentCheckpointer | None = None,
) -> AsyncIterator[AgentStreamEvent]:
    """
    Persist a user turn, stream graph tokens, then persist the validated answer.
    - load history
    - save user message
    - commit user message
    - start agent stream
    - yield tokens
    when final state arrives:
        save assistant message
        commit
        yield complete event
    
    """
    # Validate the thread ownership and the question is not blank.
    history = list(await list_messages(session, owner_id, thread_id))
    await create_message(
        session,
        thread_id=thread_id,
        owner_id=owner_id,
        role=MessageRole.USER,
        content=question,
    )
    
    # commit the message early because the streaming response might take time, and http connection can be interrupted.
    await session.commit()
    
    # Streaming agent response.
    async for event in stream_agent(
        session=session,
        owner_id=owner_id,
        thread_id=thread_id,
        query=question,
        settings=settings,
        embedding_provider=create_embedding_provider(settings),
        answer_provider=create_answer_provider(settings),
        history=history,
        checkpointer=checkpointer,
    ):
        
        if event["event"] == "token":
            yield event
            continue
        data = event["data"]
        if not isinstance(data, dict):
            raise RuntimeError("Agent completed without a final state")
        
        state = cast(AgentState, data)
        # Persist the final AI generated answer and persist the AI assistant's message in the database.
        assistant = await create_message(
            session,
            thread_id=thread_id,
            owner_id=owner_id,
            role=MessageRole.ASSISTANT,
            content=state["answer"],
            sources=state["sources"],
        )
        await session.commit()
        # Send the complete event to the client with the final state and the assistant's message.
        yield {
            "event": "complete",
            "data": {
                "thread_id": str(thread_id),
                "message_id": str(assistant.id),
                "answer": assistant.content,
                "grounded": state["grounded"],
                "sources": state["sources"],
            },
        }
