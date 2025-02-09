import dataclasses
import json
import pathlib
import sys
import textwrap
import typing


import click
from click_default_group import DefaultGroup
import llm
import sqlite_utils


# These values may need adjusting based on embedding model, question asking style, or personal preference.
RELEVANCE_CUTOFF = 0.8
COLLECTION_RESPONSE_COUNT = 3
SYSTEM_PROMPT = (
    "Answer in as few words as possible. Use a brief style with short replies."
)
OUTPUT_WIDTH = 79


def _wrap(text: str) -> str:
    return "\n".join(textwrap.wrap(text, OUTPUT_WIDTH))


def _ensure_plugin_dir() -> pathlib.Path:
    plugindir = llm.user_dir() / "questioncache"
    plugindir.mkdir(exist_ok=True)
    return plugindir


def _dbpath():
    return _ensure_plugin_dir() / "questioncache.sqlite3"


def _ensure_questions_db() -> sqlite_utils.Database:
    db = sqlite_utils.Database(_dbpath())
    return db


def _question_model() -> llm.Model:
    return llm.get_model(llm.get_default_model())


def _embedding_model() -> llm.EmbeddingModel:
    return llm.get_embedding_model(llm.get_default_embedding_model())


def _ensure_collection(db: sqlite_utils.Database) -> llm.Collection:
    return llm.Collection(
        "questioncache_questions",
        db=db,
        model=_embedding_model(),
    )


@dataclasses.dataclass
class CollectionResponse:
    score: float
    question: str
    answer: str

    def wrapped_question(self) -> str:
        return _wrap(self.question)

    def wrapped_answer(self) -> str:
        # NOTE: Not sure if this will mess up some LLM output. Definitely
        # subject to change if that's the case!
        return _wrap(self.answer)


def search_collection(
    questions_collection: llm.Collection,
    question: str,
) -> typing.List[CollectionResponse]:
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


def search_collection_exact(
    questions_collection: llm.Collection, question: str
) -> typing.Optional[CollectionResponse]:
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


def add_to_collection(
    questions_collection: llm.Collection,
    question: str,
    answer: str,
) -> None:
    """Add a question-and-answer pair to the question, to be queried in future invocations.

    Duplicate entries wil be ignored.
    """
    # TODO: add model to metadata?
    questions_collection.embed(question, question, metadata={"answer": answer})


def import_answers(questions_collection: llm.Collection, answers):
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


def send_to_llm(question_model: llm.Model, question: str) -> llm.Response:
    """Pose a question to the default LLM"""
    return question_model.prompt(question, system=SYSTEM_PROMPT)


# ---------------------------------------------------------------
# Utils for persisting data between invocations

LAST_QUESTION_KEY = "last question"
KV_TABLE_NAME = "kv"


def get_kv_table(db: sqlite_utils.Database):
    return db.create_table(
        "kv", {"key": str, "value": str}, pk="key", if_not_exists=True
    )


def save_last_question(db: sqlite_utils.Database, question: str) -> None:
    get_kv_table(db).insert({"key": LAST_QUESTION_KEY, "value": question}, replace=True)


def get_last_question(db: sqlite_utils.Database) -> typing.Optional[str]:
    from sqlite_utils.db import NotFoundError

    try:
        result = get_kv_table(db).get(LAST_QUESTION_KEY)
    except NotFoundError:
        return None
    return result["value"]


# ---------------------------------------------------------------
# CLI


def _print_with_title(title: str, body: str):
    click.secho(title, reverse=True)
    click.echo(_wrap(body))
    click.echo()


@llm.hookimpl
def register_commands(cli):
    @cli.group(cls=DefaultGroup, default="ask")
    def questioncache():
        "As questions of LLMs or of a local cache (powered by embeddings)."

    # TODO: command to extract past answers from LLM logs

    @questioncache.command()
    def db():
        "Output the path of the questioncache.db file"
        click.echo(_dbpath())

    @questioncache.command()
    def send():
        "Send the last question directly to the LLM and cache the response."
        db = _ensure_questions_db()
        if question := get_last_question(db):
            collection = _ensure_collection(db)
            if response := search_collection_exact(collection, question):
                click.secho("Already Sent", reverse=True)
                _print_with_title("Question:", response.question)
                _print_with_title("Answer:", response.answer)
            else:
                question_model = _question_model()
                _print_with_title(
                    f"Posing question to {question_model.model_id}...",
                    question,
                )

                response = send_to_llm(question_model, question)
                if question_model.can_stream:
                    for chunk in response:
                        click.echo(chunk, nl=False)
                    click.echo()
                else:
                    print(response.text())
                answer = response.text()
                add_to_collection(collection, question, answer)
                _print_with_title("Answer:", answer)
        else:
            click.secho("You haven't asked any questions yet", reverse=True)

    @click.argument("inputfile", type=click.File("r"))
    @questioncache.command()
    def importanswers(inputfile):
        "Import answers from a JSON file"
        answers = json.load(inputfile)
        click.echo(f"Importing {len(answers)} answers...")
        import_answers(_ensure_collection(_ensure_questions_db()), answers)
        click.echo("done")

    @click.argument("question", nargs=-1)
    @questioncache.command()
    def ask(question):
        "Ask a question"
        match question:
            case ("-",):
                question = sys.stdin.read()
            case _:
                question = " ".join(question)

        db = _ensure_questions_db()
        save_last_question(db, question)

        _print_with_title("Question", question)

        collection = _ensure_collection(db)
        responses = search_collection(collection, question)
        if responses:
            for idx, collection_response in enumerate(responses):
                _print_with_title(
                    f"Cached Answer {idx + 1}", collection_response.answer
                )
        else:
            question_model = _question_model()
            llm_response = send_to_llm(question_model, question)
            click.secho("Answer", reverse=True)
            if question_model.can_stream:
                for chunk in llm_response:
                    click.echo(chunk, nl=False)
                click.echo()
            else:
                _print_with_title("Answer", llm_response.text())
            answer = llm_response.text()
            add_to_collection(collection, question, answer)

    @click.confirmation_option(
        prompt="This will delete the answer cache. This cannot be undone. Continue?"
    )
    @questioncache.command()
    def clearcache():
        "Delete the answer cache"
        db = _ensure_questions_db()
        collection = _ensure_collection(db)
        collection.delete()
        click.echo("Cache cleared")
