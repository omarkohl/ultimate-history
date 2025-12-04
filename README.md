# Ultimate History

Anki deck to learn about human history. Collaboratively edited.

## Screenshots

<div class="grid" markdown>
    <img src="docs/imgs/person-picture-to-name-01-question.png" width="400" alt="Person card example">
    <img src="docs/imgs/event-name-to-summary-01-question.png" width="400" alt="Event card example">
    <img src="docs/imgs/qa-01-question.png" width="400" alt="Q&A card example">
    <img src="docs/imgs/person-related-event-01-question.png" width="400" alt="Person to related event example">
</div>

[View all screenshots](docs/screenshots.md)


## Development

```bash
# Import/export between source files and Anki
uv run main.py source-to-anki
uv run main.py anki-to-source

# Verify and fix references to people and events
uv run main.py validate
uv run main.py validate --auto-fix

# List notes by relationship count to identify highly-connected or isolated notes
uv run main.py list-relationships
uv run main.py list-relationships --sort asc --limit 10  # Show least connected
uv run main.py list-relationships --search "Napoleon"   # Filter by search term
```

## Inspiration

The note templates, the name and the general idea of collaboratively editing
high quality Anki decks are based on [Ultimate
Geography](https://github.com/anki-geo/ultimate-geography).
