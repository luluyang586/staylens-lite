"""Explicit live LLM calls. No fake local-model fallback."""
import json,time
from src.config import settings
class LLMUnavailable(RuntimeError):pass
_USAGE_EVENTS=[]


def reset_usage_events():
    _USAGE_EVENTS.clear()


def usage_summary():
    return {
        "calls":len(_USAGE_EVENTS),
        "input_tokens":sum(x.get("input_tokens") or 0 for x in _USAGE_EVENTS),
        "output_tokens":sum(x.get("output_tokens") or 0 for x in _USAGE_EVENTS),
        "total_tokens":sum(x.get("total_tokens") or 0 for x in _USAGE_EVENTS),
        "usage_available_for_all_calls":all(x.get("total_tokens") is not None for x in _USAGE_EVENTS),
    }


def complete_json(system,user,max_tokens=4000,json_schema=None,schema_name="response"):
    if not settings.has_llm:raise LLMUnavailable("请在本地.env配置LLM_API_KEY与LLM_MODEL")
    start=time.perf_counter()
    if settings.llm_provider=="anthropic":
        from anthropic import Anthropic
        client=Anthropic(api_key=settings.api_key,timeout=60,max_retries=1)
        r=client.messages.create(model=settings.llm_model,max_tokens=max_tokens,
             temperature=0,system=system,messages=[{"role":"user","content":user}])
        raw="".join(x.text for x in r.content if hasattr(x,"text"))
        input_tokens=getattr(r.usage,"input_tokens",None)
        output_tokens=getattr(r.usage,"output_tokens",None)
        _USAGE_EVENTS.append({"input_tokens":input_tokens,"output_tokens":output_tokens,
                              "total_tokens":input_tokens+output_tokens if input_tokens is not None and output_tokens is not None else None})
    elif settings.llm_provider in {"openai","openai_compatible"}:
        from openai import OpenAI
        client=OpenAI(api_key=settings.api_key,base_url=settings.base_url,timeout=60,max_retries=1)
        response_format=(
            {"type":"json_schema","json_schema":{
                "name":schema_name,"strict":True,"schema":json_schema,
            }}
            if json_schema else {"type":"json_object"}
        )
        r=client.chat.completions.create(model=settings.llm_model,
           messages=[{"role":"system","content":system},{"role":"user","content":user}],
           response_format=response_format,max_tokens=max_tokens)
        raw=r.choices[0].message.content or ""
        usage=getattr(r,"usage",None)
        _USAGE_EVENTS.append({"input_tokens":getattr(usage,"prompt_tokens",None),
                              "output_tokens":getattr(usage,"completion_tokens",None),
                              "total_tokens":getattr(usage,"total_tokens",None)})
    else:
        raise LLMUnavailable("Unsupported LLM_PROVIDER")
    if raw.strip().startswith("```"):raise ValueError("Expected JSON, received Markdown")
    return json.loads(raw)
