# Ultimate History

The aim of this project is collaborating in the creation of high quality, free and open source Anki decks on the topic of human history.

[Anki](https://apps.ankiweb.net/) is open-source [spaced repetition](https://en.wikipedia.org/wiki/Spaced_repetition) software available for Windows, macOS, Linux, Android and iOS. Check the [installations instructions](https://apps.ankiweb.net/#downloads). Spaced repetition is an improvement over classic _flashcards_ that allows for more flexible and efficient learning.

## Screenshots

<div class="grid" markdown>
    <img src="docs/imgs/person-picture-to-name-01-question.png" width="400" alt="Person card example">
    <img src="docs/imgs/event-name-to-summary-01-question.png" width="400" alt="Event card example">
    <img src="docs/imgs/qa-01-question.png" width="400" alt="Q&A card example">
    <img src="docs/imgs/person-related-event-01-question.png" width="400" alt="Person to related event example">
</div>

[View all screenshots](docs/screenshots.md)


## Contributing

Want to add historical figures, events, or improve existing cards? See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for details on how to contribute.

## Development

This project uses [brain-brew](https://github.com/ohare93/brain-brew) to bidirectionally convert between CrowdAnki JSON format and CSV files. The CrowdAnki files can be found in the `build/` directory. The CSV files under `src/data/` and the note types and templates under `src/note_models/`.

```bash
# Import/export between source files (CSV) and Anki (CrowdAnki JSON format)
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

## Inspiration & Credits

The note templates, the name and the general idea of collaboratively editing
high quality Anki decks are based on [Ultimate
Geography](https://github.com/anki-geo/ultimate-geography).
