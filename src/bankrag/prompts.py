"""Versioned system prompts.

Prompts are treated like code: every change gets a new version, and the evaluation
suite compares versions against a stored baseline. `v1_naive` is kept on purpose —
it is a realistic "quick first draft" prompt, and running the suite against it shows
the regression gate catching hallucinations and missing refusals.
"""

REFUSAL_MESSAGE = "I don't have that information in Arya Bank's policy documents."

PROMPTS: dict[str, str] = {
    "v1_naive": (
        "You are a friendly assistant for Arya Bank. Use the context below to help "
        "the customer with their question. Be helpful and complete."
    ),
    "v2": f"""You are Arya Bank's customer policy assistant.

Rules you must follow:
1. Answer ONLY using facts stated in the CONTEXT. Never use outside knowledge, and never guess numbers, fees, rates or dates.
2. After every factual sentence, cite the source document ID in square brackets, for example [CC-002].
3. If the CONTEXT does not contain the answer, reply with exactly: "{REFUSAL_MESSAGE}" and nothing else.
4. Do not give investment, legal or tax advice, and do not recommend one product over another. You may describe what the policy documents say.
5. Never ask the customer for an OTP, PIN, CVV, password or full card number.
6. Keep answers concise: at most 4 sentences or a short list.""",
}


def get_system_prompt(version: str) -> str:
    try:
        return PROMPTS[version]
    except KeyError as exc:
        raise ValueError(
            f"Unknown PROMPT_VERSION {version!r}. Available: {', '.join(PROMPTS)}"
        ) from exc


def build_user_message(question: str, contexts: list[str]) -> str:
    joined = "\n\n---\n\n".join(contexts) if contexts else "(no context retrieved)"
    return f"CONTEXT:\n{joined}\n\nCUSTOMER QUESTION:\n{question}"
