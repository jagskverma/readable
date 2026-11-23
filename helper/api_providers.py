"""API endpoints and text streaming for Readable's bring-your-own-key mode."""

from dataclasses import dataclass
import hashlib
import ipaddress
import json
import re
from urllib.error import HTTPError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import build_opener, ProxyHandler, Request

from local_model import NoRedirect

OUTPUT_LIMIT = 4096
PATHS = {
    "responses": "/responses",
    "chat": "/chat/completions",
    "chat-modern": "/chat/completions",
    "messages": "/messages",
}
CHAT_STOPS = ("stop", "eos", "end_turn", "stop_sequence")


@dataclass(frozen=True)
class Provider:
    name: str
    base: str
    protocol: str
    default_model: str = ""
    auth: str = "bearer"
    stream: bool = True

    @property
    def endpoint(self):
        return self.base + PATHS[self.protocol]

    @property
    def key_account(self):
        if self.name == "OpenAI":
            # Reuse the item written by Readable 1.5.0.
            return "OpenAI API key"
        if self.name != "Custom":
            return f"{self.name} API key"
        scope = hashlib.sha256(f"{self.base}\n{self.auth}".encode()).hexdigest()
        return f"Custom API key {scope}"

    def headers(self, key):
        if self.auth == "none":
            return {"anthropic-version": "2023-06-01"} if self.protocol == "messages" else {}
        if self.auth == "anthropic":
            return {"x-api-key": key, "anthropic-version": "2023-06-01"}
        if self.auth == "api-key":
            return {"api-key": key}
        return {"Authorization": f"Bearer {key}"}


PRESETS = {
    "openai": Provider("OpenAI", "https://api.openai.com/v1", "responses", "gpt-5-mini"),
    "openrouter": Provider("OpenRouter", "https://openrouter.ai/api/v1", "chat", "openai/gpt-5-mini"),
    "deepseek": Provider("DeepSeek", "https://api.deepseek.com", "responses", "deepseek-flash"),
    "anthropic": Provider("Anthropic", "https://api.anthropic.com/v1", "messages", "claude-haiku-4-5", "anthropic"),
    "gemini": Provider("Google Gemini", "https://generativelanguage.googleapis.com/v1beta/openai", "chat", "gemini-4-hydrogen"),
    "groq": Provider("Groq", "https://api.groq.com/openai/v1", "chat-modern"),
    "mistral": Provider("Mistral", "https://api.mistral.ai/v1", "chat", "mistral-small-latest"),
    "xai": Provider("xAI", "https://api.x.ai/v1", "responses"),
    "together": Provider("Together AI", "https://api.together.ai/v1", "chat"),
    "fireworks": Provider("Fireworks AI", "https://api.fireworks.ai/inference/v1", "chat"),
    "cerebras": Provider("Cerebras", "https://api.cerebras.ai/v1", "chat"),
    "kimi": Provider("Kimi", "https://api.moonshot.ai/v1", "chat"),
}


def loopback(host):
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def custom_provider(base, protocol, auth, stream=True):
    if not re.fullmatch(r"[!-~]+", base) or "\\" in base or "?" in base or "#" in base:
        raise ValueError("Enter a base URL without spaces, query parameters or fragments.")
    parsed = urlsplit(base)
    hostname = parsed.hostname
    port = parsed.port
    if (not hostname or parsed.username is not None or parsed.password is not None
            or (parsed.scheme != "https" and not (parsed.scheme == "http" and loopback(hostname)))):
        raise ValueError("Use an HTTPS base URL, or HTTP on your own loopback address. Do not put credentials in the URL.")
    if protocol not in PATHS:
        raise ValueError("Choose a supported API format.")
    if auth not in ("bearer", "api-key", "anthropic", "none"):
        raise ValueError("Choose a supported authentication method.")
    if auth == "none" and not loopback(hostname):
        raise ValueError("Only a loopback server can be configured without an API key.")
    if (protocol == "messages") != (auth == "anthropic") and auth != "none":
        raise ValueError("Anthropic Messages uses an Anthropic API key.")
    if type(stream) is not bool:
        raise ValueError("Streaming must be on or off.")
    hostname_display = f"[{hostname}]" if ":" in hostname else hostname
    default_port = 443 if parsed.scheme == "https" else 80
    netloc = f"{hostname_display}:{port}" if port is not None and port != default_port else hostname_display
    path = parsed.path.rstrip("/")
    if any(path.endswith(endpoint) for endpoint in PATHS.values()):
        raise ValueError("Enter the base URL without /responses, /messages, or /chat/completions.")
    return Provider("Custom", urlunsplit((parsed.scheme, netloc, path, "", "")), protocol,
                    auth=auth, stream=stream)


def from_settings(settings):
    provider = settings.get("provider", "openai")
    if provider == "custom":
        return custom_provider(settings["base_url"], settings["protocol"], settings["auth"], settings.get("stream", True))
    if provider not in PRESETS:
        raise ValueError("Select a valid API provider using Install.command --configure.")
    return PRESETS[provider]


def payload_for(provider, model, instruction, source):
    payload = {"model": model, "stream": provider.stream}
    user = {"role": "user", "content": source}
    if provider.protocol == "responses":
        payload.update(instructions=instruction, input=[user], store=False, max_output_tokens=OUTPUT_LIMIT)
        if provider.name == "OpenAI" and model == provider.default_model:
            payload["reasoning"] = {"effort": "minimal"}
        if provider.name == "DeepSeek":
            payload["reasoning"] = {"effort": "none"}
    elif provider.protocol == "messages":
        payload.update(system=instruction, messages=[user], max_tokens=OUTPUT_LIMIT)
    else:
        payload["messages"] = [{"role": "system", "content": instruction}, user]
        payload["max_completion_tokens" if provider.protocol == "chat-modern" else "max_tokens"] = OUTPUT_LIMIT
    return payload


def request(provider, payload, headers):
    req = Request(provider.endpoint, data=json.dumps(payload).encode(),
                  headers={**headers, "Content-Type": "application/json"})
    handlers = [NoRedirect()]
    if loopback(urlsplit(provider.base).hostname):
        handlers.append(ProxyHandler({}))
    try:
        return build_opener(*handlers).open(req, timeout=150)
    except HTTPError as exc:
        exc.close()
        messages = {
            401: "rejected the API key. Check it in Install.command --configure.",
            403: "denied this request. Check the key and model permissions.",
            404: "could not find that model or endpoint. Check your setup.",
            429: "hit a rate or quota limit. Check usage and billing.",
        }
        if 300 <= exc.code < 400:
            raise RuntimeError(f"{provider.name} redirected the request. Check the configured endpoint.") from None
        message = messages.get(exc.code, f"could not complete the request (HTTP {exc.code}).")
        raise RuntimeError(f"{provider.name} {message}") from None


def events(stream):
    """Yield SSE data records, ignoring comments and other metadata fields."""
    data = []
    for raw in stream:
        line = raw.rstrip(b"\r\n")
        if not line:
            if data:
                yield b"\n".join(data)
                data.clear()
        elif line.startswith(b"data:"):
            data.append(line[5:].lstrip(b" "))
    if data:
        yield b"\n".join(data)


def content(value):
    if isinstance(value, str):
        return value
    return "".join(part["text"] for part in (value or [])
                   if part.get("type") in ("text", "output_text"))


def json_text(protocol, result):
    if protocol == "responses" and result.get("status") == "completed":
        return "".join(content(item.get("content")) for item in result["output"] if item.get("type") == "message")
    if protocol == "messages" and result.get("stop_reason") in CHAT_STOPS:
        return content(result["content"])
    if protocol in ("chat", "chat-modern"):
        choice = result["choices"][0]
        if choice.get("finish_reason") in CHAT_STOPS:
            return content(choice["message"]["content"])
    raise ValueError("The response did not complete.")


def stream_text(protocol, stream, name):
    finished = False
    for data in events(stream):
        if data == b"[DONE]":
            if protocol in ("chat", "chat-modern"):
                return
            break
        event = json.loads(data)
        kind = event.get("type")
        if event.get("error") or kind in ("error", "response.failed", "response.incomplete"):
            raise RuntimeError(f"{name} could not complete this section.")
        if protocol == "responses":
            if kind == "response.output_text.delta":
                yield event["delta"]
            elif kind == "response.completed":
                return
        elif protocol == "messages":
            if kind == "content_block_delta" and event["delta"].get("type") == "text_delta":
                yield event["delta"]["text"]
            elif kind == "content_block_start" and event["content_block"].get("type") == "text":
                yield event["content_block"]["text"]
            elif kind == "message_delta":
                reason = event["delta"].get("stop_reason")
                if reason is not None and reason not in CHAT_STOPS:
                    raise RuntimeError(f"{name} stopped before completing this section.")
            elif kind == "message_stop":
                return
        else:
            choices = event.get("choices") or []
            if not choices:
                continue
            choice = choices[0]
            text = content(choice.get("delta", {}).get("content"))
            if text:
                yield text
            reason = choice.get("finish_reason")
            if reason:
                if reason not in CHAT_STOPS:
                    raise RuntimeError(f"{name} stopped before completing this section.")
                finished = True
    if not finished:
        raise RuntimeError(f"{name} disconnected before completing this section.")


def deltas(provider, model, instruction, source, headers):
    with request(provider, payload_for(provider, model, instruction, source), headers) as response:
        if not provider.stream or response.headers.get_content_type() == "application/json":
            yield json_text(provider.protocol, json.load(response))
        else:
            yield from stream_text(provider.protocol, response, provider.name)
