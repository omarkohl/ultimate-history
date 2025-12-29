# Ultimate History Project

Anki deck for learning human history, collaboratively edited.

## Project Structure

- `main.py` - Task runner for common commands
- `recipes/` - Brainbrew recipes for Anki import/export
- `src/data/` - Raw data used to generate Anki decks (edit these)
- `src/note_models/` - Note type and card type templates (HTML, CSS)
- `build/` - Generated Anki decks for CrowdAnki plugin (DO NOT edit manually or read it)

## Common Commands

Use `uv run main.py <command>`:
- `source-to-anki` - Export source files to Anki
- `anki-to-source` - Import Anki changes back to source

## Development Workflow

- Use `uv` for running Python code
- Use `jj` for version control
- Edit files in `src/`, never modify or read `build/` directly
- `build/` contains CrowdAnki format decks, only modified by running `uv run main.py source-to-anki`

## Personal Fields

- **Personal fields are always empty**: Columns like `personal related person 1-3`, `personal related event 1-3`, and `personal notes` exist for Anki users to add their own notes locally. They are never used in this project and should be left empty in exports.

## Python Code Standards

- **Always** run Python scripts with `uv run <script>` (never with plain `python`)
- **Always** format and lint code with `uv run ruff check --fix` and `uv run ruff format` before committing
- **Always** write CSV files with these exact settings:
  ```python
  csv.DictWriter(
      f,
      fieldnames=fieldnames,
      lineterminator="\n",
      quoting=csv.QUOTE_ALL,
      escapechar=None,
      doublequote=True,
  )
  ```
