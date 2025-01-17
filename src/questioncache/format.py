import typing
import rich

if typing.TYPE_CHECKING:
    from . import CollectionResponse


def as_table(
    responses: "typing.List[CollectionResponse]",
) -> rich.table.Table:
    """Format a list of CollectionResponses for printing to the console."""
    table = rich.table.Table()
    table.add_column("Relevance")
    table.add_column("Question", no_wrap=False)
    table.add_column("Answer", no_wrap=False)
    for response in responses:
        table.add_row(
            f"{response.score:<.5}",
            rich.text.Text(response.question),
            rich.text.Text(response.answer),
            end_section=True,
        )
    return table


def print(content):
    console = rich.console.Console()
    console.print(content)
