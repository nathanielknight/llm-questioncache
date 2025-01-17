import llm
import sqlite_utils

import dataclasses
import pathlib
import typing

# ------------------------------------------------------------------------------------------------
# Setup
appdir = llm.user_dir() / "questioncache"
if not (appdir.exists() and appdir.is_dir()):
    appdir.mkdir()

db = sqlite_utils.Database(pathlib.Path(appdir) / "questions.sqlite3")

embedding_model = llm.get_embedding_model(llm.get_default_embedding_model())
question_model = llm.get_model(llm.get_default_model())
questions_collection = llm.Collection(
    "questioncache_questions", db=db, model=embedding_model
)


# ------------------------------------------------------------------------------------------------
# Question collection

# These values may need adjusting based on embedding model, question asking style, or personal preference.
RELEVANCE_CUTOFF = 0.8
COLLECTION_RESPONSE_COUNT = 3


@dataclasses.dataclass
class CollectionResponse:
    score: float
    question: str
    answer: str


def search_collection(question: str) -> typing.List[CollectionResponse]:
    responses = questions_collection.similar(
        question, number=2 * COLLECTION_RESPONSE_COUNT
    )
    relevant_responses = [
        CollectionResponse(
            score=r.score,
            question=r.id,
            answer=r.metadata["answer"],
        )
        for r in responses
        if r.score and r.score > RELEVANCE_CUTOFF and r.metadata
    ]
    relevant_responses.sort(key=lambda r: r.score, reverse=True)
    return relevant_responses[:COLLECTION_RESPONSE_COUNT]


def search_collection_exact(question: str) -> typing.Optional[CollectionResponse]:
    """Query for an _exact_ question in the responses collection."""
    import json
    from sqlite_utils.db import NotFoundError

    responses_table = questions_collection.db["embeddings"]
    try:
        response = responses_table.get((questions_collection.id, question))
        answer = json.loads(response["metadata"])["answer"]
        return CollectionResponse(score=1.0, question=question, answer=answer)
    except NotFoundError:
        return None


def add_to_collection(question: str, answer: str) -> None:
    """Add a question-and-answer pair to the question, to be queried in future invocations.

    Duplicate entries wil be ignored.
    """
    questions_collection.embed(question, question, metadata={"answer": answer})


def import_answers(answers):
    """Add a list of past answers as dicts with 'question' and 'answer' to the collection."""
    batch_size = 32
    questions_collection.embed_multi_with_metadata(
        entries=(
            (
                str(answer["question"]),
                str(answer["question"]),
                {"answer": answer["answer"]},
            )
            for answer in answers
        ),
        batch_size=batch_size,
    )


# ------------------------------------------------------------------------------------------------
# Asking questions of the LLM
SYSTEM_PROMPT = (
    "Answer in as few words as possible. Use a brief style with short replies."
)


def send_to_llm(question: str) -> llm.Response:
    """Pose a question to the default LLM"""
    return question_model.prompt(question, system=SYSTEM_PROMPT)


# ------------------------------------------------------------------------------------------------
# Key value store for plugin state
LAST_QUESTION_KEY = "last question"
KV_TABLE_NAME = "kv"


def get_kv_table():
    return db.create_table(
        "kv", {"key": str, "value": str}, pk="key", if_not_exists=True
    )


def save_last_question(question: str) -> None:
    get_kv_table().insert({"key": LAST_QUESTION_KEY, "value": question}, replace=True)


def get_last_question() -> typing.Optional[str]:
    from sqlite_utils.db import NotFoundError

    try:
        result = get_kv_table().get(LAST_QUESTION_KEY)
    except NotFoundError:
        return None
    return result["value"]
