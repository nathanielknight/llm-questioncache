# llm-questioncache

A plugin for [llm](https://llm.datasette.io/) for sending questions
to LLMs and getting succinct answers. It also saves answers in a
SQLite database along with embeddings of the corresponding questions
and will answer future, similar questions from the cache rather than
the LLM.

## Installation

```bash
llm install llm-questioncache
```

## Usage

The plugin adds a new `questioncache` command group to `llm`. See `llm questioncache --help` for the full list of subcommands.

### Ask a Question

```bash
llm questioncache ask "What is the capital of France?"
```

This will:
1. Check if similar questions exist in the cache
2. If found, show the cached answers
3. If not found, ask the LLM and cache the response

You can also pipe questions through stdin:
```bash
echo "What is the capital of France?" | llm questioncache ask -
```

### Send Last Question Directly to LLM

To bypass the cache and send the last asked question directly to the LLM:

```bash
llm questioncache send
```

You might have to do this if you've previously asked a similar-but-distinct
question

### Import Previous Answers

You can import a collection of previous questions and answers from a JSON file:

```bash
llm questioncache importanswers answers.json
```

The JSON file should contain an array of objects with `question` and `answer` fields.

If you've been using LLM in this way already you might have some useful answers already.
To retrieve and format all the LLM responses with a particular system prompt, use `sqlite-utils`:

```sh
uvx sqlite-utils "$(llm logs path)" "select prompt as question, response as answer from responses where system = 'Answer in as few words as possible. Use a brief style with short replies.'"
```

### Clear the Cache

To delete all cached questions and answers:

```bash
llm questioncache clearcache
```

## Configuration

The plugin uses your default LLM and embedding models as configured in `llm`. No additional configuration is required.

Key parameters (configured in the code):
- Relevance cutoff for similar questions: 0.8
- Number of similar answers to show: 3
- System prompt for brief answers: "Answer in as few words as possible. Use a brief style with short replies."


## Shell integration

You might find it useful to create a shell script to succinctly invoke `llm questioncache`:

For example, save this as `~/.local/bin/q`:

```
#!/usr/bin/env sh
llm questioncache $*
```

You can now pose questions with:

```sh
q how do you exit vim
```
