# Contributing to Ultimate History

Contributions are welcome! You can help by adding new historical figures and events, or improving existing cards.

Note that this guide refers exclusively to modifying the content of the cards, for example fix an incorrect birth date, rewrite the summary of a historical event or add a new historical person. For larger or structural changes see the "Development" section of the main [README.md](../README.md).

## Two Ways to Contribute

### Option 1: Edit CSV Files

1. **Fork and clone** this repository ([GitHub guide](https://docs.github.com/en/get-started/quickstart/fork-a-repo))
2. **Edit CSV files** (for example using _Microsoft Excel_) in `src/data/`:
   - `person.csv` - Historical figures
   - `event.csv` - Historical events
   - `qa.csv` - Question & answer cards
   - `cloze.csv` - Cloze deletion cards
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

## Tagging System

Tags allow users to filter the deck for specific topics they want to study. All tags follow the format `UH::<Category>::<Value>` with three categories: **Region**, **Period**, and **Theme**.

### Principles

1. **Every card needs at least one Region and one Period tag** - This ensures users can filter by geography and time
2. **Theme tags are optional** but helpful for cross-cutting topics
3. **Use the most specific applicable tag** - A card about Beethoven should use `UH::Region::Europe::Western`, not just `UH::Region::Europe`
4. **Multiple tags are fine** - Events spanning regions/periods should have multiple tags

### Region Tags (Hierarchical)

Regions use a 2-level hierarchy. Always use the most specific level that applies.

| Level 1 | Level 2 Options |
|---------|-----------------|
| `UH::Region::Europe` | `Western`, `Eastern`, `Northern`, `Southern`, `Central` |
| `UH::Region::Asia` | `East`, `Southeast`, `South`, `Central`, `West` (Middle East) |
| `UH::Region::Africa` | `North`, `West`, `East`, `Central`, `Southern` |
| `UH::Region::Americas` | `North`, `Central`, `South`, `Caribbean` |
| `UH::Region::Oceania` | `Australia`, `Pacific` |
| `UH::Region::Global` | *(no sub-regions)* - For truly worldwide events |

**Examples:**
- French Revolution → `UH::Region::Europe::Western`
- Mongol Empire → `UH::Region::Asia::Central` + `UH::Region::Asia::East` + `UH::Region::Europe::Eastern`
- World War II → `UH::Region::Global`
- Meiji Restoration → `UH::Region::Asia::East`

### Period Tags (Centuries)

Use century tags for all content. For ancient history, use "BCE" suffix.

| Tag | Approximate Coverage |
|-----|---------------------|
| `UH::Period::Prehistory` | Before 3000 BCE |
| `UH::Period::4th_Millennium_BCE` | 4000-3001 BCE |
| `UH::Period::30th_Century_BCE` ... | Individual centuries BCE |
| `UH::Period::1st_Century` | 1-100 CE |
| `UH::Period::2nd_Century` ... | Individual centuries CE |
| `UH::Period::21st_Century` | 2001-2100 |

**Guidelines:**
- Use the century when the event **primarily occurred**, not when it started
- For events spanning centuries, use multiple tags
- For persons, tag based on their **active period**, not just birth/death

**Examples:**
- Napoleon (1769-1821) → `UH::Period::18th_Century` + `UH::Period::19th_Century`
- WWI (1914-1918) → `UH::Period::20th_Century`
- Roman Republic (509-27 BCE) → Multiple century tags as appropriate for specific content

### Theme Tags (Curated List)

Themes categorize content by subject matter. Use the current approved list:

| Tag | Use For |
|-----|---------|
| `UH::Theme::War` | Battles, conflicts, military history, conquests |
| `UH::Theme::Politics` | Governance, diplomacy, revolutions, political movements |
| `UH::Theme::Economy` | Trade, industry, economic systems, commerce |
| `UH::Theme::Society` | Social movements, daily life, demographics, social structures |
| `UH::Theme::Culture` | Art, literature, music, architecture, cultural movements |
| `UH::Theme::Science` | Technology, medicine, scientific discoveries, inventions |
| `UH::Theme::Religion` | Faiths, religious movements, theology, religious conflicts |

**Guidelines:**
- Most cards should have 1-2 themes; avoid over-tagging
- If a theme doesn't fit, don't force it - Region and Period are sufficient
- New themes require discussion via GitHub issue before being added

### Tag Examples

| Content | Tags |
|---------|------|
| Napoleon Bonaparte | `UH::Region::Europe::Western`, `UH::Period::18th_Century`, `UH::Period::19th_Century`, `UH::Theme::War`, `UH::Theme::Politics` |
| Industrial Revolution | `UH::Region::Europe::Western`, `UH::Period::18th_Century`, `UH::Period::19th_Century`, `UH::Theme::Economy`, `UH::Theme::Science` |
| Confucius | `UH::Region::Asia::East`, `UH::Period::6th_Century_BCE`, `UH::Period::5th_Century_BCE`, `UH::Theme::Religion` |
| Silk Road | `UH::Region::Asia::Central`, `UH::Region::Asia::East`, `UH::Region::Europe`, `UH::Theme::Economy` |

## Need Help?

- New to GitHub? [First contributions guide](https://github.com/firstcontributions/first-contributions)
- Questions? Open an [issue](https://github.com/omarkohl/ultimate-history/issues)
