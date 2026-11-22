# Readable for Brave

Readable rewrites the prose on a web page in place. Click **R** to start, click again to restore the original, and click a third time to reuse the saved rewrite. If the site changes a paragraph, Readable rewrites that paragraph and reuses the others. It preserves code blocks and link targets.

## Install on macOS

1. Download or clone this repository. You need desktop Brave and Python 3.9 or newer with pip and venv.
2. Run `bash /path/to/Readable/Install.command` in Terminal. The installer prints the extension folder and opens it in Finder.
3. In `brave://extensions`, turn on **Developer mode**, click **Load unpacked**, and select `~/Library/Application Support/Readable/extension`. Pin Readable to the toolbar. If it is already installed, reload its extension card after updating.
4. Choose one of the rewrite options below. Open an article and click **R**.

### On this Mac with Ollama

This option works without a ChatGPT account or API key.

1. Install and start [Ollama for macOS](https://docs.ollama.com/macos). Download a local text model, for example `ollama pull qwen3:4b`.
2. Run `bash /path/to/Readable/Use-local-model.command` and press Return for the suggested model, or enter another model already installed in Ollama.
3. Leave Ollama running. Readable connects to `127.0.0.1:11434` and refuses Ollama cloud models. Once the model is downloaded, local rewrites can run offline. Speed and wording depend on the model and your Mac.

### With a ChatGPT plan

Run `bash /path/to/Readable/Sign-in.command`. Sign in on OpenAI’s site and approve plan usage. Successful sign-in selects ChatGPT for new rewrites.

OpenAI currently documents eligible **Plus and Pro** accounts for this open-source integration. A Free account’s sign-in does not provide rewrite usage. Availability and usage limits are set by OpenAI. See [OpenAI’s developer guide](https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt) and [ChatGPT usage settings](https://chatgpt.com/settings/usage).

## Data and storage

- A toolbar click starts the rewrite. Readable may include prose below the fold and limited nearby context for inline formatting.
- In ChatGPT mode, Readable sends the text to OpenAI under the connected account. Local mode sends it to the Ollama server on this Mac.
- Rewrites are saved in the Brave profile. The cache is shared by both modes, holds up to 5,000 text blocks, and reuses matching blocks across visits. It can contain text from pages you rewrite. The source wording used by the toggle is kept in the current tab.
- OpenAI credentials are stored under the current macOS user’s `Library/Application Support/Readable` directory. The project does not include account credentials. The `key` in the extension manifest is a public key that keeps the unpacked extension ID stable.

Readable works on rendered HTML. To include a collapsed section, expand it before clicking. PDFs, frames, and canvas content are outside its scope.

## Troubleshooting and uninstall

If Brave can’t find the native host, rerun the installer. Brave on macOS reads `~/Library/Application Support/Google/Chrome/NativeMessagingHosts/local.readable.rewriter.json`. Its `allowed_origins` must contain the Readable ID shown in `brave://extensions`, and its `path` must point to the executable `run-helper`.

To uninstall, remove Readable from Brave, disconnect Readable in ChatGPT settings if you used ChatGPT, then remove the Readable app support folder and the native host manifest above. Older versions also used the Brave profile root’s `NativeMessagingHosts` folder.

## Development

Run `python3 -m unittest discover -s tests` to check the local backend’s response validation and handling of remote models. Use `for script in *.command; do bash -n "$script" || break; done` to check the shell scripts.

Readable is an independent project. [MIT license](LICENSE).
