# Ultimate History

Anki deck to learn about human history. Collaboratively edited.

## Screenshots

<img src="docs/imgs/person-picture-to-name-01-question.png" width="400" alt="Person card example">
<img src="docs/imgs/event-when-01-question.png" width="400" alt="Event card example">
<img src="docs/imgs/qa-01-question.png" width="400" alt="Q&A card example">
<img src="docs/imgs/cloze-01-question.png" width="400" alt="Cloze card example">

[View all screenshots](docs/screenshots.md)


## Development

```bash
uv run main.py source-to-anki
uv run main.py anki-to-source

# Verify and fix references to people and events
uv run main.py validate
uv run main.py validate --auto-fix
```

## Inspiration

The note templates, the name and the general idea of collaboratively editing
high quality Anki decks are based on [Ultimate
Geography](https://github.com/anki-geo/ultimate-geography).
