# Contributing to Ultimate History

Contributions are welcome! You can help by adding new historical figures and events, or improving existing cards.

Note that this guide refers exclusively to modifying the content of the cards, for example fix an incorrect birth date, rewrite the summary of a historical event or add a new historical person. For larger or structural changes see the "Development" section of the main [README.md](../README.md).

## Two Ways to Contribute

### Option 1: Edit CSV Files

1. **Fork and clone** this repository ([GitHub guide](https://docs.github.com/en/get-started/quickstart/fork-a-repo))
2. **Edit CSV files** (for example using _Microsoft Excel_) in `src/data/`:
   - `Ultimate History | Person.csv` - Historical figures
   - `Ultimate History | Event.csv` - Historical events
   - `Ultimate History | QA.csv` - Question & answer cards
   - `Ultimate History | Cloze.csv` - Cloze deletion cards
3. **Ignore the GUID column** - it will be auto-generated later by the project maintainers
4. **Submit a pull request** ([GitHub guide](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request))

### Option 2: Edit in Anki

1. **Install [CrowdAnki](https://ankiweb.net/shared/info/1788670778)** plugin in Anki
2. **Import** the deck from the `build/` directory in this repository
3. **Make your edits** in Anki
4. **Export** using CrowdAnki to the `build/` directory
5. **Fork and submit a pull request** with your changes (see above)

## Guidelines

- Ensure facts are accurate and sourced
- Keep descriptions concise but informative
- Use proper date formats and ranges
- Link related people and events
- Do not use copyrighted content

## Need Help?

- New to GitHub? [First contributions guide](https://github.com/firstcontributions/first-contributions)
- Questions? Open an [issue](https://github.com/omarkohl/ultimate-history/issues)
