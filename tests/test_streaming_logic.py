#!/usr/bin/env python3
"""Test streaming logic with mock data."""

import asyncio
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.models.types import StreamChunk


async def test_streaming_logic():
    """Test the streaming demo logic with mock chunks."""

    print("\n" + "=" * 60)
    print("🧪 Testing Streaming Logic (Mock Data)")
    print("=" * 60 + "\n")

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

    print("🔄 Processing mock chunks...\n")

    for chunk in mock_chunks:
        chunk_count += 1

        # Handle thinking/reasoning content
        if chunk.is_thinking and chunk.reasoning_content:
            if not is_thinking:
                print("\033[93m🧠 Thinking:\033[0m")
                is_thinking = True

            print(f"\033[93m{chunk.reasoning_content}\033[0m", end="", flush=True)
            thinking_buffer.append(chunk.reasoning_content)

        # Handle answer content
        elif chunk.content and not chunk.is_thinking:
            if is_thinking and not answer_buffer:
                print("\n\n\033[97m💡 Answer:\033[0m")
                is_thinking = False

            print(f"{chunk.content}", end="", flush=True)
            answer_buffer.append(chunk.content)

        # Handle completion
        if chunk.is_complete:
            if "error" in chunk.metadata:
                print(f"\n\n\033[91m❌ Error: {chunk.metadata['error']}\033[0m")
            elif "usage" in chunk.metadata:
                usage = chunk.metadata["usage"]
                print(f"\n\n\033[90m📊 Tokens: {usage.get('total_tokens', 'N/A')} "
                      f"(prompt: {usage.get('prompt_tokens', 'N/A')}, "
                      f"completion: {usage.get('completion_tokens', 'N/A')})\033[0m")

    print("\n")
    print("=" * 60)
    print("✨ Test Complete")
    print("=" * 60)
    print(f"Total chunks received: {chunk_count}")
    print(f"Thinking length: {len(''.join(thinking_buffer))} chars")
    print(f"Answer length: {len(''.join(answer_buffer))} chars")

    # Verify results
    print("\n" + "=" * 60)
    print("🔍 Verification")
    print("=" * 60)

    assert chunk_count == 5, f"Expected 5 chunks, got {chunk_count}"
    assert len(''.join(thinking_buffer)) == 63, "Thinking buffer incorrect"
    assert len(''.join(answer_buffer)) == 58, "Answer buffer incorrect"
    assert is_thinking == False, "Should have transitioned from thinking to answer"

    print("✅ All assertions passed!")
    print("✅ Streaming logic is correct!")
    print("\n📝 Note: Your current model (Kimi-K2) doesn't support reasoning_content.")
    print("   To see actual thinking mode, use OpenAI o1 models or similar.")


if __name__ == "__main__":
    asyncio.run(test_streaming_logic())
