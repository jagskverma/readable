# Readable

Readable rewrites web pages in place in Chrome and Brave on macOS. Click **R** to start, click again to restore the original, and click a third time to reuse the saved rewrite. If the site changes a paragraph, Readable rewrites that paragraph and reuses the others. It preserves code blocks and link targets.

## Before you install

**The default setup requires an eligible ChatGPT Plus or Pro plan.** ChatGPT Free sign-in does not include rewrite usage. To use Readable without a ChatGPT plan, choose the optional local Ollama setup. Bring-your-own-API-key support is planned for a future release. [OpenAI’s plan usage guide](https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt)

## Install on macOS

1. Download and extract the [latest release ZIP](https://github.com/jagskverma/readable-for-brave/releases/latest). You need Google Chrome or Brave and [Python 3.9 or newer](https://www.python.org/downloads/macos/).
2. Open `Install.command` from the extracted folder. You can also type `bash ` in Terminal, drag `Install.command` into the window, and press Return. Choose a rewrite provider first. Setup then installs the helper and opens the extension folder and the extensions page in Chrome or Brave.
3. Open `chrome://extensions` in Chrome or `brave://extensions` in Brave. Turn on **Developer mode**, click **Load unpacked**, and select the extension folder that setup shows. Then pin Readable and click **R** on an article. If Readable is already installed, click **Reload** on its extension card.

Choose **ChatGPT** to sign in on OpenAI’s site and approve plan usage. Choose **Ollama** to run rewrites on your Mac without a ChatGPT account or API key. [Install Ollama](https://ollama.com/download/mac) if needed. Setup can download the suggested local model with your approval if the Ollama command line tool is installed. Once the model is downloaded, the Mac can rewrite offline. Leave Ollama running while you use Readable.

Rerunning setup keeps your existing provider. To change providers later, run `Install.command --configure` with Bash.

OpenAI sets account eligibility and limits. To manage plan usage after connecting Readable, see [ChatGPT usage settings](https://chatgpt.com/settings/usage).

## Data and storage

- A toolbar click starts the rewrite. Readable may include prose below the fold and limited nearby context for inline formatting.
- In ChatGPT mode, Readable sends the text to OpenAI under the connected account. Local mode sends it to the Ollama server on this Mac.
- Rewrites are saved in the browser profile. The cache is shared by both modes, holds up to 5,000 text blocks, and reuses matching blocks across visits. It can contain text from pages you rewrite. The source wording used by the toggle is kept in the current tab.
- OpenAI credentials are stored under the current macOS user’s `Library/Application Support/Readable` directory. The project does not include account credentials. The `key` in the extension manifest is a public key that keeps the unpacked extension ID stable.

Readable works on rendered HTML. To include a collapsed section, expand it before clicking. PDFs, frames, and canvas content are outside its scope.

## Troubleshooting and uninstall

If the browser can’t find the native host, rerun the installer. Chrome and Brave on macOS both read `~/Library/Application Support/Google/Chrome/NativeMessagingHosts/local.readable.rewriter.json`. Its `allowed_origins` must contain the Readable ID shown on the extensions page, and its `path` must point to the executable `run-helper`.

To uninstall, remove Readable from your browser, disconnect Readable in ChatGPT settings if you used ChatGPT, then remove the Readable app support folder and the native host manifest above. Older versions also used the Brave profile root’s `NativeMessagingHosts` folder.

## Development

Run `python3 -m unittest discover -s tests` to check the local backend’s response validation and handling of remote models. Use `bash -n Install.command` and `bash -n installer/configure-ollama.sh` to check the shell scripts.

Readable is an independent project. [MIT license](LICENSE).
