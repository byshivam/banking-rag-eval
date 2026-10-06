"""Ask the assistant a question from the command line.

Usage: python -m bankrag.ask "What is the late payment fee on a ₹10,000 bill?"
"""

import sys

from bankrag.rag import RAGAssistant


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit('Usage: python -m bankrag.ask "your question"')
    response = RAGAssistant().answer(" ".join(sys.argv[1:]))
    print(response.answer)
    print("\nRetrieved:")
    for hit in response.retrieved:
        print(f"  {hit.score:.2f}  {hit.chunk.chunk_id}  {hit.chunk.section}")
    print(f"\n({response.model}, prompt {response.prompt_version}, {response.latency_s}s)")


if __name__ == "__main__":
    main()
