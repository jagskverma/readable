"""Provider configuration and API keys stored in the macOS login Keychain."""

import getpass
import re
import sys
import warnings
from urllib.parse import urlsplit

import api_providers

SERVICE = "Readable"


def keychain(operation, account, *args):
    # Choose macOS explicitly. A third-party keyring backend may use a file.
    try:
        from keyring.backends.macOS import Keyring
        from keyring.errors import KeyringError
    except ImportError:
        raise RuntimeError("Mac Keychain support is unavailable. Rerun Install.command.") from None
    try:
        return getattr(Keyring(), operation)(SERVICE, account, *args)
    except (KeyringError, AttributeError, OSError):
        raise RuntimeError("Readable could not access the macOS Keychain. Check that your login Keychain is unlocked.") from None


def read_choice(prompt, choices, default=None):
    for index, label in enumerate(choices, start=1):
        print(f"  {index}. {label}")
    choice = input(prompt).strip()
    if not choice and default is not None:
        return default
    if choice not in {str(n) for n in range(1, len(choices) + 1)}:
        raise ValueError("Enter one of the listed numbers.")
    return int(choice) - 1


def read_configuration():
    if not sys.stdin.isatty():
        raise RuntimeError("Run Install.command --configure in an interactive Terminal to enter your API key.")
    providers = api_providers.PRESETS
    selected = read_choice("Provider [1]: ", [p.name for p in providers.values()] + ["Custom endpoint"], 0)
    if selected < len(providers):
        slug, provider = list(providers.items())[selected]
        settings = {"backend": "api-key", "provider": slug}
    else:
        base = input("Endpoint base URL: ").strip()
        protocols = list(api_providers.PATHS)
        protocol = protocols[read_choice("API format [1]: ",
                                         ["Responses", "Chat Completions (max_tokens)",
                                          "Chat Completions (max_completion_tokens)", "Anthropic Messages"], 0)]
        local = api_providers.loopback(urlsplit(base).hostname)
        if protocol == "messages":
            auth_methods = {"anthropic": "Anthropic API key"}
        else:
            auth_methods = {"bearer": "Bearer API key", "api-key": "api-key header (Azure compatible)"}
        if local:
            auth_methods["none"] = "No API key (loopback only)"
        auth = list(auth_methods)[read_choice("Authentication [1]: ", list(auth_methods.values()), 0)]
        stream = input("Stream rewrites? [Y/n]: ").strip().lower()
        if stream not in ("", "y", "yes", "n", "no"):
            raise ValueError("Choose yes or no for streaming.")
        provider = api_providers.custom_provider(base, protocol, auth, stream not in ("n", "no"))
        settings = {"backend": "api-key", "provider": "custom", "base_url": provider.base,
                    "protocol": provider.protocol, "auth": provider.auth, "stream": provider.stream}

    label = f" [{provider.default_model}]" if provider.default_model else ""
    model = input(f"{provider.name} model ID{label}: ").strip() or provider.default_model
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9._:/@-]{0,255}", model):
        raise ValueError("Enter a valid model ID from the selected provider.")
    settings["model"] = model
    print(f"Readable will send uncached prose to {provider.endpoint}. Usage may be billed by that provider.")
    if provider.auth == "none":
        return settings, provider, None

    # Fail closed if this terminal cannot turn off echo.
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        try:
            key = getpass.getpass(f"{provider.name} API key (hidden): ").strip()
        except getpass.GetPassWarning:
            raise RuntimeError("Unable to hide input. Run setup in Terminal.") from None
    if not re.fullmatch(r"[!-~]{1,4096}", key):
        raise ValueError("Enter an API key without spaces or control characters.")
    if provider.name == "OpenAI" and not key.startswith("sk-"):
        raise ValueError("Enter an OpenAI API key from platform.openai.com/api-keys.")
    return settings, provider, key


def save_key(provider, key):
    if key is not None:
        keychain("set_password", provider.key_account, key)


def authorization(provider):
    if provider.auth == "none":
        return provider.headers(None)
    key = keychain("get_password", provider.key_account)
    if not key:
        raise RuntimeError(f"No {provider.name} API key is saved for this endpoint. Run Install.command --configure.")
    return provider.headers(key)


def remove_key(provider):
    if provider.auth != "none" and keychain("get_password", provider.key_account):
        keychain("delete_password", provider.key_account)
