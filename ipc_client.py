import requests
import json
from PySide6.QtWidgets import QMessageBox

HACHIMI_URL = "http://127.0.0.1:50433"

def send_command(command: dict, show_error: bool = True) -> dict | None:
    try:
        response = requests.post(
            HACHIMI_URL,
            data=json.dumps(command),
            headers={'Content-Type': 'application/json'},
            timeout=2
        )
        response.raise_for_status()

        cmd_response = response.json()
        if cmd_response.get("type") == "Error":
            error_message = cmd_response.get("message", "Unknown error. Check Hachimi logs.")
            print(f"Hachimi IPC Error: {error_message}")
            if show_error:
                QMessageBox.warning(None, "Hachimi IPC Error", error_message)
            return None

        print(f"IPC command '{command['type']}' sent successfully.")
        return cmd_response

    except requests.exceptions.RequestException as e:
        error_text = f"Could not connect to Hachimi IPC.\n\n- Is the game running with Hachimi injected?\n- Is the IPC server enabled in Hachimi's config?\n\nError: {e}"
        print(f"IPC Error: {error_text}")
        if show_error:
            QMessageBox.critical(None, "Hachimi Connection Error", error_text)
        return None

def story_goto_block(block_index: int):
    print(f"Sending StoryGotoBlock command for index: {block_index}")
    command = {
        "type": "StoryGotoBlock",
        "block_id": block_index,
        "incremental": False
    }
    send_command(command)

def reload_localized_data():
    print("Sending ReloadLocalizedData command.")
    command = {"type": "ReloadLocalizedData"}
    if send_command(command):
        QMessageBox.information(None, "IPC Success", "Hachimi has reloaded the translation files.")