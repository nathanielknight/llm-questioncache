An LLM plugin to efficiently pose questions to LLMs, cache the answers, and quickly retrieve answers to questions that you've already posed.


# Importing past questions

```sh
sqlite-utils "$(llm logs path)" "select prompt as question, response as answer from responses where system = 'Answer in as few words as possible. Use a brief style with short replies.'" | py -m questioncache -i
```
