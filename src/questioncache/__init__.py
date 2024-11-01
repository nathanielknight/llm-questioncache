import llm
import rich
import sqlite_utils

import dataclasses
import pathlib
import typing

# ------------------------------------------------------------------------------------------------
# Setup and constants
SYSTEM_PROMPT = (
    "Answer in as few words as possible. Use a brief style with short replies."
)
COLLECTION_RESPONSE_COUNT = 6

appdir = llm.user_dir() / "questioncache"

db = sqlite_utils.Database(pathlib.Path(appdir) / "questions.sqlite3")

embedding_model = llm.get_embedding_model(llm.get_default_embedding_model())
question_model = llm.get_model(llm.get_default_model())
questions_collection = llm.Collection(
    "questioncache_questions", db=db, model=embedding_model
)

# ------------------------------------------------------------------------------------------------
# Interacting with the LLM or the Embedding Collection


@dataclasses.dataclass
class CollectionResponse:
    score: float
    question: str
    answer: str


def ask_collection(question: str) -> typing.List[CollectionResponse]:
    # TODO: figure out what the relevance cutoff should be and add it
    embedding = embedding_model.embed(question)
    responses = questions_collection.similar_by_vector(
        embedding, number=COLLECTION_RESPONSE_COUNT
    )
    return [
        CollectionResponse(
            score=response.score,
            question=response.id,
            answer=response.metadata["answer"],
        )
        for response in responses
    ]


def ask_llm(question: str) -> llm.Response:
    return question_model.prompt(question, system=SYSTEM_PROMPT)


def add_to_collection(question: str, answer: str) -> None:
    questions_collection.embed(question, question, metadata={"answer": answer})


def format_responses_as_table(
    responses: typing.List[CollectionResponse],
) -> rich.table.Table:
    table = rich.table.Table()
    table.add_column("Relevance")
    table.add_column("Question", no_wrap=False)
    table.add_column("Answer", no_wrap=False)
    for score, question, answer in responses:
        table.add_row(
            f"{score:<.5}",
            rich.text.Text(question),
            rich.text.Text(answer),
            end_section=True,
        )
    return table


if __name__ == "__main__":
    responses = ask_collection("what's up with bats")
    console = rich.console.Console()
    table = format_responses_as_table(responses)
    console.print(table)
