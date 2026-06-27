import httpx
import pytest
import asyncio

@pytest.mark.anyio
async def test_probe_providers():
    keys = {
        "openmodel": "om-ofTzdidDb78yhzRKuMYrZBreJAq4hWU863Z1KkVG5",
        "nvidia_prefix": "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",
        "modal": "modalresearch_TzUJFpXlhpM9zxRhymgDm4DZmIT_IFDGYuPtZT9Eekg"
    }

    async with httpx.AsyncClient() as client:
        # 1. OpenModel Responses detail
        print("\n=== TESTING OPENMODEL RESPONSES DETAIL ===")
        url = "https://api.openmodel.ai/v1/responses"
        headers = {"Authorization": f"Bearer {keys['openmodel']}", "Content-Type": "application/json"}
        body = {
            "model": "qwen3.6-plus",
            "input": "How many r-s are in strawberry?"
        }
        try:
            resp = await client.post(url, headers=headers, json=body, timeout=20)
            print("Status:", resp.status_code)
            print("Full JSON:")
            import json
            print(json.dumps(resp.json(), indent=2))
        except Exception as e:
            print("Failed:", e)

        # 2. Nvidia NIM with prefixed key
        print("\n=== TESTING NVIDIA NIM WITH PREFIXED KEY ===")
        url_nv_models = "https://integrate.api.nvidia.com/v1/models"
        headers_nv = {"Authorization": f"Bearer {keys['nvidia_prefix']}", "Content-Type": "application/json"}
        try:
            resp_nv = await client.get(url_nv_models, headers=headers_nv, timeout=10)
            print("Nvidia Models Status with Prefix:", resp_nv.status_code)
            if resp_nv.status_code == 200:
                data = resp_nv.json().get("data", [])
                nv_models = [m.get("id") for m in data]
                print(f"Total prefixed models: {len(nv_models)}")
                # Try completions with first few models
                url_nv_chat = "https://integrate.api.nvidia.com/v1/chat/completions"
                for target_model in nv_models[:3]:
                    print(f"Testing Nvidia model: {target_model}")
                    body_nv = {
                        "model": target_model,
                        "messages": [{"role": "user", "content": "Say hello"}],
                        "max_tokens": 50
                    }
                    resp_chat = await client.post(url_nv_chat, headers=headers_nv, json=body_nv, timeout=15)
                    print(f"Model {target_model} Status: {resp_chat.status_code}")
                    print(f"Model {target_model} Response: {resp_chat.text[:400]}")
            else:
                print("Nvidia models failed:", resp_nv.text)
        except Exception as e:
            print("Failed Nvidia prefixed:", e)




