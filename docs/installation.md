# Installation & Updates

## Installing the Deck

There are three ways to install the Ultimate History deck:

### Option 1: Download from AnkiWeb

1. Install [Anki](https://apps.ankiweb.net/) if you haven't already
2. Download the deck from AnkiWeb: https://ankiweb.net/shared/info/1816180599
3. Double-click the downloaded `.apkg` file, or go to File > Import in Anki

This is the simplest method for most users.

### Option 2: Download from GitHub Releases

1. Install [Anki](https://apps.ankiweb.net/)
2. Go to the [Releases page](https://github.com/omarkohl/ultimate-history/releases)
3. Download the latest `.apkg` file
4. Double-click the downloaded file, or go to File > Import in Anki

### Option 3: Import from Git Repository

This method is recommended if you plan to contribute to the deck or want to stay on the latest version with maximum flexibility.

1. Install [Anki](https://apps.ankiweb.net/)
2. Install the [CrowdAnki plugin](https://ankiweb.net/shared/info/1788670778):
   - In Anki, go to Tools > Add-ons
   - Click "Get Add-ons..."
   - Enter code: `1788670778`
   - Click OK and restart Anki
3. Clone this repository:
   ```bash
   git clone https://github.com/omarkohl/ultimate-history.git
   ```
4. In Anki, go to File > CrowdAnki: Import from disk
5. Select the appropriate directory in `build/` (e.g., `build/Ultimate_History/`)

## Updating the Deck

### If You Installed from AnkiWeb or GitHub Releases

Simply download the latest version and import it as described above. Anki will update your existing deck while preserving your learning progress.

This will overwrite any changes to the cards you made, including to the **personal fields**! To support the personal fields you need to use the CrowdAnki plugin.

### If You're Using the Git Repository

1. Pull the latest changes:
   ```bash
   git pull
   ```
2. In Anki, go to File > CrowdAnki: Import from disk
3. Select the directory in `build/` again
4. Select the personal fields you want to preserve (see below)

The import will update the deck while preserving your learning statistics (review history, intervals, etc.).

#### Protecting Personal Fields During Updates

The Ultimate History deck includes several "Personal" fields where you can add your own notes:

- Personal Notes
- Personal Related Person 1
- Personal Related Person 2
- Personal Related Event 1
- Personal Related Event 2

**To prevent these fields from being overwritten when updating:**

1. When importing with CrowdAnki, the import dialog will appear
2. Look for the option to mark fields as "Personal"
3. Check the boxes for any Personal fields where you've added content
4. You only need to check fields that you've actually modified

## Troubleshooting

### Data Loss

Rely on the automatic Anki backups. File > Revert to Backup.

### Getting Help

If you encounter issues, please [open an issue](https://github.com/omarkohl/ultimate-history/issues) on GitHub.
