"""Test streaming logic with mock data."""

import pytest

from src.models.types import StreamChunk


@pytest.mark.asyncio
async def test_streaming_logic():
    """Test the streaming demo logic with mock chunks."""

    # Simulate a response with thinking followed by answer
    mock_chunks = [
        # Thinking phase
        StreamChunk(reasoning_content="Let me think about this...",
                    is_thinking=True,
                    is_complete=False,
                    chunk_index=1),
        StreamChunk(reasoning_content="The answer involves multiple factors.",
                    is_thinking=True,
                    is_complete=False,
                    chunk_index=2),
        # Transition to answer
        StreamChunk(content="Based on my analysis,",
                    is_thinking=False,
                    is_complete=False,
                    chunk_index=3),
        StreamChunk(content=" here is the answer to your question.",
                    is_thinking=False,
                    is_complete=False,
                    chunk_index=4),
        # Completion
        StreamChunk(is_complete=True,
                    chunk_index=5,
                    metadata={
                        "usage": {
                            "prompt_tokens": 10,
                            "completion_tokens": 20,
                            "total_tokens": 30
                        }
                    }),
    ]

    thinking_buffer = []
    answer_buffer = []
    is_thinking = False
    chunk_count = 0

    for chunk in mock_chunks:
        chunk_count += 1

        # Handle thinking/reasoning content
        if chunk.is_thinking and chunk.reasoning_content:
            if not is_thinking:
                is_thinking = True
            thinking_buffer.append(chunk.reasoning_content)

        # Handle answer content
        elif chunk.content and not chunk.is_thinking:
            if is_thinking:
                is_thinking = False
            answer_buffer.append(chunk.content)

    # Verify results
    assert chunk_count == 5, f"Expected 5 chunks, got {chunk_count}"
    assert "".join(
        thinking_buffer
    ) == "Let me think about this...The answer involves multiple factors.", "Thinking buffer incorrect"
    assert "".join(
        answer_buffer
    ) == "Based on my analysis, here is the answer to your question.", "Answer buffer incorrect"
    assert is_thinking is False, "Should have transitioned from thinking to answer"
