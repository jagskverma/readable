"""Store Readable's optional OpenAI API key in the macOS login Keychain."""

import getpass
import re
import sys

SERVICE = "Readable"
ACCOUNT = "OpenAI API key"
DEFAULT_MODEL = "gpt-5-mini"


def keychain(operation, *args):
    # Choose macOS explicitly. A third-party keyring backend may use a file.
    try:
        from keyring.backends.macOS import Keyring
        from keyring.errors import KeyringError
    except ImportError:
        raise RuntimeError("Mac Keychain support is unavailable. Rerun Install.command.") from None
    try:
        return getattr(Keyring(), operation)(SERVICE, ACCOUNT, *args)
    except (KeyringError, AttributeError, OSError):
        raise RuntimeError("Readable could not access the macOS Keychain. Check that your login Keychain is unlocked.") from None


def read_configuration():
    if not sys.stdin.isatty():
        raise RuntimeError("Run Install.command --configure in an interactive Terminal to enter your API key.")
    model = input(f"OpenAI API model [{DEFAULT_MODEL}]: ").strip() or DEFAULT_MODEL
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", model):
        raise RuntimeError("Enter a valid OpenAI API model ID.")
    # Fail closed if this terminal cannot turn off echo.
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        try:
            key = getpass.getpass("OpenAI API key (hidden): ").strip()
        except getpass.GetPassWarning:
            raise RuntimeError("Unable to hide input. Run setup in Terminal.") from None
    if not re.fullmatch(r"sk-[A-Za-z0-9_-]+", key):
        raise RuntimeError("Enter an OpenAI API key from platform.openai.com/api-keys.")
    return model, key


def save_key(key):
    keychain("set_password", key)


def authorization():
    key = keychain("get_password")
    if not key:
        raise RuntimeError("No OpenAI API key is saved. Run Install.command --configure and choose OpenAI API key.")
    return {"Authorization": "Bearer " + key}


def remove_key():
    if keychain("get_password"):
        keychain("delete_password")
