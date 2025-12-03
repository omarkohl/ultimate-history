# Ultimate History

Anki deck to learn about human history. Collaboratively edited.

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
