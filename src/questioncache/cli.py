import sys
import json

from . import (
    search_collection,
    search_collection_exact,
    question_model,
    send_to_llm,
    add_to_collection,
    import_answers,
    get_last_question,
    save_last_question,
)


def get_question() -> str:
    """Get input:
    - from sys.argv if there's nothing on STDIN
    - from STDIN if there's input available
    """
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    else:
        return " ".join(sys.argv[1:])


def _ask_question_of_llm_and_print(question):
    save_last_question(question)
    response = send_to_llm(question)
    if question_model.can_stream:
        for chunk in response:
            print(chunk, end="")
            sys.stdout.flush()
        print()
    else:
        print(response.text())
    answer = response.text()
    add_to_collection(question, answer)
    sys.exit(0)


def pose_to_collection():
    question = get_question()
    save_last_question(question)
    responses = search_collection(question)
    if not responses:
        print(f"cache miss; asking {question_model.model_id}")
        _ask_question_of_llm_and_print(question)
    else:
        from . import format

        table = format.as_table(responses)
        format.print(table)
        print(f"{sys.argv[0]} -s to send to the {question_model}")
    sys.exit(0)


def send_last_question_to_llm():
    if question := get_last_question():
        if response := search_collection_exact(question):
            from . import format

            print("already sent")
            format.print(format.as_table([response]))
        else:
            print(f"posing last question to {question_model}:\n\n{question}\n\n")
            _ask_question_of_llm_and_print(question)
    else:
        print("you haven't asked any questions yet")
    sys.exit(0)


def import_responses_from_stdin():
    answers = json.load(sys.stdin)
    print(f"import {len(answers)} answers... ", end="", flush=True)
    import_answers(answers)
    print("done.")
    sys.exit(0)


def print_usage():
    print("this is where the usage will go")
    sys.exit(0)


def cli():
    match sys.argv[1:]:
        case ["-i"] | ["--import"]:
            import_responses_from_stdin()
        case ["-s"] | ["--send"]:
            send_last_question_to_llm()
        case ["-l"] | ["--last"]:
            print(get_last_question())
        case ["-"]:
            pose_to_collection()
        case [] | ["-h"] | ["--help"]:
            print_usage()
        case _:
            pose_to_collection()
