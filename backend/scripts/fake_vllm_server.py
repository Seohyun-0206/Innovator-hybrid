#!/usr/bin/env python3
"""vLLM OpenAI-호환 API를 흉내 내는 로컬 fake 서버.

실제 vLLM 서버 없이도 apps/providers/vllm.py의 VLLMProvider가 의도한 대로
동작하는지(SSE 스트리밍, TTFT/usage 파싱, /metrics KV cache 파싱) 확인하기
위한 개발용 스텁입니다. 표준 라이브러리만 사용해서 별도 설치 없이 바로
실행할 수 있습니다.

사용법:
    python scripts/fake_vllm_server.py --port 8100

그 다음 백엔드가 이 서버를 바라보도록 .env 또는 환경변수를 맞추세요:
    VLLM_BASE_URL=http://127.0.0.1:8100/v1
    VLLM_API_KEY=          (비워두면 인증 없이 통과)

--chunk-delay-ms로 스트리밍 청크 사이 지연을 늘리면 TTFT/TPOT 값이 0에
가깝지 않고 눈에 보이는 값으로 나옵니다.
"""
import argparse
import json
import random
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

FAKE_ANSWERS = ["A", "B", "C", "D"]


class FakeVLLMHandler(BaseHTTPRequestHandler):
    server_version = "FakeVLLM/1.0"
    chunk_delay_ms = 30

    def log_message(self, format, *args):
        print(f"[fake-vllm] {self.address_string()} - {format % args}")

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")
        if path.endswith("/metrics"):
            self._handle_metrics()
        elif path.endswith("/models"):
            self._handle_models()
        else:
            self.send_error(404, "not found")

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/")
        if path.endswith("/chat/completions"):
            self._handle_chat_completions()
        else:
            self.send_error(404, "not found")

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw or b"{}")

    def _handle_models(self):
        body = json.dumps({"object": "list", "data": [{"id": "fake-model", "object": "model"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_metrics(self):
        usage = round(random.uniform(0.05, 0.85), 4)
        text = (
            "# HELP vllm:gpu_cache_usage_perc GPU KV-cache usage.\n"
            "# TYPE vllm:gpu_cache_usage_perc gauge\n"
            f"vllm:gpu_cache_usage_perc {usage}\n"
        )
        body = text.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_chat_completions(self):
        payload = self._read_json_body()
        model = payload.get("model", "fake-model")
        messages = payload.get("messages") or []
        prompt = messages[-1]["content"] if messages else ""
        stream = bool(payload.get("stream", False))

        print(f"[fake-vllm] === incoming request ===")
        print(f"[fake-vllm] model: {model}")
        print(f"[fake-vllm] messages ({len(messages)}):")
        for message in messages:
            print(f"[fake-vllm]   [{message.get('role')}] {message.get('content')}")
        print(f"[fake-vllm] prompt (last message content):\n{prompt}")
        print(f"[fake-vllm] =========================")

        reply_text = self._build_reply(prompt)
        prompt_tokens = max(1, len(prompt.split()))
        completion_tokens = max(1, len(reply_text.split()))

        if not stream:
            self._respond_non_streaming(model, reply_text, prompt_tokens, completion_tokens)
            return
        self._respond_streaming(model, reply_text, prompt_tokens, completion_tokens)

    def _respond_non_streaming(self, model, reply_text, prompt_tokens, completion_tokens):
        body = json.dumps(
            {
                "id": "fake-chatcmpl",
                "object": "chat.completion",
                "model": model,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": reply_text}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                },
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _respond_streaming(self, model, reply_text, prompt_tokens, completion_tokens):
        # Content-Length도 chunked encoding도 안 쓰므로, 클라이언트가 본문 끝을 알 수 있는
        # 유일한 신호는 연결 종료입니다. close_connection을 안 켜두면 requests/curl이
        # [DONE] 이후에도 소켓이 닫히길 무한정 기다리며 멈춥니다.
        self.close_connection = True
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        # 첫 토큰 전에 살짝 지연을 줘서 TTFT가 0이 아니라 실제로 측정되는 값으로 보이게 합니다.
        time.sleep(self.chunk_delay_ms / 1000)
        words = reply_text.split(" ")
        for index, word in enumerate(words):
            chunk = word if index == 0 else f" {word}"
            event = {
                "id": "fake-chatcmpl",
                "object": "chat.completion.chunk",
                "model": model,
                "choices": [{"index": 0, "delta": {"content": chunk}, "finish_reason": None}],
            }
            self._write_event(event)
            time.sleep(self.chunk_delay_ms / 1000)

        final_event = {
            "id": "fake-chatcmpl",
            "object": "chat.completion.chunk",
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }
        self._write_event(final_event)
        self.wfile.write(b"data: [DONE]\n\n")

    def _write_event(self, event: dict):
        line = f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        self.wfile.write(line.encode("utf-8"))
        self.wfile.flush()

    def _build_reply(self, prompt: str) -> str:
        # 객관식 프롬프트(A/B/C/D 정답 요구)면 정답 형식으로, 라우팅 프롬프트(small/large 판단)면
        # small/large로 답합니다. 그 외에는 일반 텍스트 응답을 돌려줍니다.
        if re.search(r"A, B, C, D", prompt):
            return f"정답: {random.choice(FAKE_ANSWERS)}"
        if "small" in prompt and "large" in prompt:
            return random.choice(["small", "large"])
        return "이것은 fake vLLM 서버의 응답입니다."


def main():
    parser = argparse.ArgumentParser(description="vLLM OpenAI-호환 API를 흉내 내는 로컬 fake 서버")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8100)
    parser.add_argument(
        "--chunk-delay-ms",
        type=int,
        default=30,
        help="스트리밍 청크 사이 지연(ms) — TTFT/TPOT 값을 눈으로 확인하고 싶을 때 늘리세요",
    )
    args = parser.parse_args()

    FakeVLLMHandler.chunk_delay_ms = args.chunk_delay_ms
    server = ThreadingHTTPServer((args.host, args.port), FakeVLLMHandler)
    print(f"Fake vLLM server listening on http://{args.host}:{args.port}")
    print(f"  chat completions: http://{args.host}:{args.port}/v1/chat/completions")
    print(f"  metrics:          http://{args.host}:{args.port}/metrics")
    print("Ctrl+C로 종료하세요.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
