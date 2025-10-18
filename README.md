# PeraPera Translation Toolkit

PeraPera is an all-in-one translation toolkit, designed to work with the [Hachimi](https://github.com/Hachimi-Hachimi/Hachimi) mod. It provides a full suite of tools, including a graphical editor, for extracting, translating, and building game assets.

## Features

-   **Graphical Editor:** A full-featured GUI for editing story files, database text, and generated assets.
-   **Asset Extraction:** Dumps game text and assets into a human-readable JSON workspace.
-   **Hachimi Build System:** Builds a clean, Hachimi-compatible `localized_data` directory from your workspace.
-   **Automated Translations (Autofill):** Automatically translates repetitive text like birthdays, character pieces, secret headers, and more.
-   **Community Data Import:** Imports translations from external sources like GameTora (APIs and web scraping) and other Hachimi projects.
-   **Generated Image Assets:** Automatically generates translated gacha banner names and comment images from your text.
-   **Live Game Sync:** Instantly jump to a story block in-game while you're editing it.

## Installation

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/Mario0051/PeraPera
    cd PeraPera
    ```

2.  **Install Dependencies:**
    It is highly recommended to use a Python virtual environment.
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    pip install -r requirements.txt
    ```

## Configuration

Before first use, you must configure `perapera_config.ini`. The tool will create a default version on its first run.

1.  Run the tool once: `python perapera.py`
2.  Open the newly created `perapera_config.ini`.
3.  Ensure the `game_data_directory` path points to a folder with a `master` directory and a `meta` file. The tool will attempt to auto-detect this.

## Workflow

The typical translation workflow is as follows:

1.  **Launch the GUI:**
    ```bash
    python editor_gui_qt.py
    ```

2.  **Dump Game Data:**
    In the GUI, click the **"Dump All Tables"** button. This reads the game's `master.mdb` and populates your `translations/` workspace with JSON files.

3.  **Run Autofills:**
    Click the **"Run All Autofills"** button. This will automatically translate a significant amount of simple, repetitive text based on rules and existing data.

4.  **Translate:**
    -   Use the **Asset Tree** on the left to navigate to a story file or database table.
    -   Double-click to open it in a new tab.
    -   Fill in the English text fields. Your work is saved automatically when you switch tabs or files (or manually with `Ctrl+S`).
    -   Use the workflow tools like **"Next Dialogue"** and **"Manage Speakers"** to speed up the process.

5.  **Build:**
    When you are ready to test your translations, click the **"Build for Hachimi"** button. This will generate a `build/localized_data` folder that you can use for Hachimi.

6.  **Hot Reload:**
    If the game is running with Hachimi's IPC server enabled, you can click the **"Hot Reload"** button to make the game reload your translation files without a restart.

---

## Credits

This project was made possible by adapting features and learning from several fantastic open-source tools in the community:

-   **@LeadRDRK**
    - [ZokuZoku](https://github.com/Hachimi-Hachimi/ZokuZoku)
    - [node-cricodecs](https://github.com/LeadRDRK/node-cricodecs)
-   **@KevinVG207** - [Uma-Carotene-TL](https://github.com/KevinVG207/Uma-Carotene-TL)
-   **@noccu** - [umamusu-translate](https://github.com/noccu/umamusu-translate)
-   **@MarshmallowAndroid** - [UmamusumeExplorer](https://github.com/MarshmallowAndroid/UmamusumeExplorer)
-   **@mos9527** - [PyCriCodecsEx](https://github.com/mos9527/PyCriCodecsEx)
