import os
import json
import time
import datetime
import tempfile
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

try:
    from config import load_config
except ImportError:
    from .config import load_config

try:
    from providers import get_provider
except ImportError:
    from .providers import get_provider

# Global start time for uptime calculation
START_TIME = time.time()

# File paths
STATS_FILE = os.path.join(os.path.dirname(__file__), "usage_stats.json")

class UsageTracker:
    """
    Subcomponent responsible for persisting and loading usage telemetry to disk.
    Manages historical sliding windows of requests and daily logs.
    """
    def __init__(self):
        self.history: List[Dict[str, Any]] = [] # Sliding history of recent requests
        self.daily_history: Dict[str, Dict[str, int]] = {} # YYYY-MM-DD -> stats
        self.model_stats: Dict[str, Dict[str, Any]] = {} # model_id -> cumulative stats
        self.load_stats()

    def load_stats(self) -> None:
        if os.path.exists(STATS_FILE):
            try:
                with open(STATS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.history = data.get("history", [])
                    self.daily_history = data.get("daily_history", {})
                    self.model_stats = data.get("model_stats", {})
            except Exception:
                pass

    def save_stats(self) -> None:
        data = {
            "history": self.history[-100:], # keep only last 100 requests in file to limit size
            "daily_history": self.daily_history,
            "model_stats": self.model_stats
        }
        fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(STATS_FILE), prefix="stats_temp_", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            os.replace(temp_path, STATS_FILE)
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    def record_rate_limit(self, model: str) -> None:
        if not model:
            return
        if model not in self.model_stats:
            self.model_stats[model] = {
                "requests": 0, "input_tokens": 0, "output_tokens": 0,
                "success_count": 0, "error_count": 0, "latency_sum": 0.0,
                "rate_limit_events": 0, "errors": [],
                "tool_calls_attempted": 0, "tool_calls_succeeded": 0
            }
        self.model_stats[model]["rate_limit_events"] = self.model_stats[model].get("rate_limit_events", 0) + 1
        self.save_stats()

    def record_tool_execution(self, model: str, success: bool) -> None:
        if not model:
            return
        if model not in self.model_stats:
            self.model_stats[model] = {
                "requests": 0, "input_tokens": 0, "output_tokens": 0,
                "success_count": 0, "error_count": 0, "latency_sum": 0.0,
                "rate_limit_events": 0, "errors": [],
                "tool_calls_attempted": 0, "tool_calls_succeeded": 0
            }
        stats = self.model_stats[model]
        stats["tool_calls_attempted"] = stats.get("tool_calls_attempted", 0) + 1
        if success:
            stats["tool_calls_succeeded"] = stats.get("tool_calls_succeeded", 0) + 1
        self.save_stats()

    def record_request(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency: float,
        success: bool,
        error_msg: Optional[str] = None,
        is_retry: bool = False,
        prompt_profile: Optional[Any] = None,
        request_id: Optional[str] = None
    ) -> None:
        now_ts = time.time()
        record = {
            "timestamp": now_ts,
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency": latency,
            "success": success,
            "error": error_msg,
            "is_retry": is_retry,
            "request_id": request_id or ""
        }
        if prompt_profile:
            if hasattr(prompt_profile, "model_dump"):
                record["prompt_profile"] = prompt_profile.model_dump()
            elif hasattr(prompt_profile, "dict"):
                record["prompt_profile"] = prompt_profile.dict()
            else:
                record["prompt_profile"] = prompt_profile
        else:
            record["prompt_profile"] = {
                "system_prompt_tokens": input_tokens,
                "context_tokens": 0,
                "memory_tokens": 0,
                "tool_tokens": 0,
                "user_message_tokens": 0,
                "total_prompt_tokens": input_tokens,
                "baseline_tokens": input_tokens
            }
        self.history.append(record)

        if model:
            if model not in self.model_stats:
                self.model_stats[model] = {
                    "requests": 0, "input_tokens": 0, "output_tokens": 0,
                    "success_count": 0, "error_count": 0, "latency_sum": 0.0,
                    "rate_limit_events": 0, "errors": [],
                    "tool_calls_attempted": 0, "tool_calls_succeeded": 0
                }
            stats = self.model_stats[model]
            stats["requests"] = stats.get("requests", 0) + 1
            stats["input_tokens"] = stats.get("input_tokens", 0) + input_tokens
            stats["output_tokens"] = stats.get("output_tokens", 0) + output_tokens
            if success:
                stats["success_count"] = stats.get("success_count", 0) + 1
                stats["latency_sum"] = stats.get("latency_sum", 0.0) + latency
            else:
                stats["error_count"] = stats.get("error_count", 0) + 1
                if error_msg:
                    if "errors" not in stats:
                        stats["errors"] = []
                    stats["errors"].append(error_msg)
                    if len(stats["errors"]) > 5:
                        stats["errors"] = stats["errors"][-5:]
        
        # Clean history in-memory to last 1000 items
        if len(self.history) > 1000:
            self.history = self.history[-1000:]
            
        # Update daily statistics
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        if today_str not in self.daily_history:
            self.daily_history[today_str] = {
                "requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "success": 0,
                "failure": 0
            }
            
        day_stats = self.daily_history[today_str]
        day_stats["requests"] += 1
        day_stats["input_tokens"] += input_tokens
        day_stats["output_tokens"] += output_tokens
        if success:
            day_stats["success"] += 1
        else:
            day_stats["failure"] += 1
            
        self.save_stats()


class StatisticsManager:
    """
    Subcomponent responsible for calculating live session, daily, and cumulative statistics.
    """
    def __init__(self, tracker: UsageTracker):
        self.tracker = tracker
        self.session_requests = 0
        self.session_success = 0
        self.session_failure = 0
        self.session_input_tokens = 0
        self.session_output_tokens = 0
        self.session_retries = 0
        self.session_latencies: List[float] = []

    def record_session_request(self, success: bool, input_tokens: int, output_tokens: int, latency: float, is_retry: bool = False) -> None:
        self.session_requests += 1
        if success:
            self.session_success += 1
        else:
            self.session_failure += 1
        if is_retry:
            self.session_retries += 1
        self.session_input_tokens += input_tokens
        self.session_output_tokens += output_tokens
        self.session_latencies.append(latency)
        if len(self.session_latencies) > 100:
            self.session_latencies = self.session_latencies[-100:]

    def get_avg_latency(self) -> float:
        # Use last 20 requests in history for moving average
        recent = self.tracker.history[-20:]
        latencies = [r["latency"] for r in recent if r["success"] and r["latency"] > 0]
        if latencies:
            return sum(latencies) / len(latencies)
        return 0.0

    def get_daily_stats(self) -> Dict[str, int]:
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        return self.tracker.daily_history.get(today_str, {
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "success": 0,
            "failure": 0
        })

    def get_total_cumulative_stats(self) -> Dict[str, int]:
        totals = {
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "success": 0,
            "failure": 0
        }
        for day, stats in self.tracker.daily_history.items():
            totals["requests"] += stats.get("requests", 0)
            totals["input_tokens"] += stats.get("input_tokens", 0)
            totals["output_tokens"] += stats.get("output_tokens", 0)
            totals["success"] += stats.get("success", 0)
            totals["failure"] += stats.get("failure", 0)
        return totals


class ProviderMonitor:
    """
    Subcomponent responsible for tracking provider configuration, availability, and launcher heartbeat.
    """
    def __init__(self):
        self.last_launcher_heartbeat: float = 0.0

    def record_launcher_heartbeat(self) -> None:
        self.last_launcher_heartbeat = time.time()

    def get_launcher_status(self) -> str:
        if time.time() - self.last_launcher_heartbeat < 5.0:
            return "Active (Connected)"
        return "Inactive (Not Connected)"

    def check_provider_availability(self, provider_name: str) -> bool:
        p_name = provider_name.lower().strip()
        if p_name == "gemini":
            load_dotenv(override=True)
            return bool(os.getenv("GEMINI_API_KEY"))
        elif p_name == "mock":
            return True
        return False


class RateLimiter:
    """
    Subcomponent responsible for verifying limits (RPM, TPM, RPD) and delaying or queueing requests.
    """
    def __init__(self, tracker: UsageTracker):
        self.tracker = tracker

    def check_limits(self, provider: str, estimated_tokens: int) -> Optional[str]:
        """
        Proactively check configured limits.
        Returns None if fine, or a message describing the limit status.
        """
        config = load_config()
        providers_conf = config.get("providers", {})
        prov_limits = providers_conf.get(provider, {}).get("rate_limits", {})
        
        if not prov_limits:
            return None
            
        limit_rpm = prov_limits.get("requests_per_minute", 15)
        limit_tpm = prov_limits.get("tokens_per_minute", 1000000)
        limit_rpd = prov_limits.get("requests_per_day", 1500)
        
        now = time.time()
        
        # 1. RPD Check
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        today_stats = self.tracker.daily_history.get(today_str, {})
        today_reqs = today_stats.get("requests", 0)
        if today_reqs >= limit_rpd:
            return "daily_quota_exceeded"
            
        # 2. RPM & TPM Proactive Window Check
        recent = [r for r in self.tracker.history if now - r["timestamp"] < 60.0]
        recent_req_count = len(recent)
        recent_token_count = sum(r["input_tokens"] + r["output_tokens"] for r in recent)
        
        if recent_req_count >= limit_rpm:
            return "rpm_exceeded"
            
        if recent_token_count + estimated_tokens >= limit_tpm:
            return "tpm_exceeded"
            
        return None

    def get_proactive_wait_time(self, provider: str, estimated_tokens: int) -> float:
        """
        Calculate the sleep duration required to satisfy RPM/TPM limits.
        """
        config = load_config()
        providers_conf = config.get("providers", {})
        prov_limits = providers_conf.get(provider, {}).get("rate_limits", {})
        
        if not prov_limits:
            return 0.0
            
        limit_rpm = prov_limits.get("requests_per_minute", 15)
        limit_tpm = prov_limits.get("tokens_per_minute", 1000000)
        
        now = time.time()
        recent = [r for r in self.tracker.history if now - r["timestamp"] < 60.0]
        if not recent:
            return 0.0
            
        wait_times = []
        
        # If RPM exceeded, wait until the oldest request in the window is older than 60s
        if len(recent) >= limit_rpm:
            oldest_req = recent[0]
            wait_for_rpm = 60.0 - (now - oldest_req["timestamp"]) + 0.1
            wait_times.append(max(0.0, wait_for_rpm))
            
        # If TPM exceeded, wait until enough tokens slide out of the window
        recent_tokens = sum(r["input_tokens"] + r["output_tokens"] for r in recent)
        if recent_tokens + estimated_tokens >= limit_tpm:
            tokens_accum = 0
            for r in recent:
                tokens_accum += r["input_tokens"] + r["output_tokens"]
                if recent_tokens - tokens_accum + estimated_tokens < limit_tpm:
                    wait_for_tpm = 60.0 - (now - r["timestamp"]) + 0.1
                    wait_times.append(max(0.0, wait_for_tpm))
                    break
                    
        if wait_times:
            return max(wait_times)
        return 0.0


class ResourceManager:
    """
    Public single-gateway component for tracking AI usage, rate limits, and configuration.
    Contains internal subcomponents as implementation details.
    """
    _instance: Optional['ResourceManager'] = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ResourceManager, cls).__new__(cls, *args, **kwargs)
            cls._instance._init_manager()
        return cls._instance

    def _init_manager(self):
        self.tracker = UsageTracker()
        self.statistics = StatisticsManager(self.tracker)
        self.monitor = ProviderMonitor()
        self.limiter = RateLimiter(self.tracker)
        # Diagnostics state – updated by update_diagnostics()
        self.last_request_context_dict: Optional[Dict[str, Any]] = None
        self.last_successful_request_id: Optional[str] = None
        self.last_exception_message: Optional[str] = None

    def record_launcher_heartbeat(self) -> None:
        self.monitor.record_launcher_heartbeat()

    def record_rate_limit_event(self, model: str) -> None:
        self.tracker.record_rate_limit(model)

    def record_tool_execution(self, model: str, success: bool) -> None:
        self.tracker.record_tool_execution(model, success)

    def update_diagnostics(self, ctx: Any) -> None:
        """
        Called after a request completes (success or failure) to capture
        the RequestContext for the /api/diagnostics endpoint.
        """
        try:
            self.last_request_context_dict = ctx.to_diagnostics_dict()
            if ctx.response_status == "success":
                self.last_successful_request_id = ctx.request_id
            if ctx.last_exception:
                self.last_exception_message = ctx.last_exception
        except Exception:
            pass

    def get_stats(self) -> Dict[str, Any]:
        """
        Aggregate stats into a clean REST-consumable format.
        """
        config = load_config()
        provider = config.get("provider", "gemini")
        model = config.get("model", "gemini-2.5-flash")
        
        daily_stats = self.statistics.get_daily_stats()
        cumulative_stats = self.statistics.get_total_cumulative_stats()
        
        providers_conf = config.get("providers", {})
        limit_rpd = providers_conf.get(provider, {}).get("rate_limits", {}).get("requests_per_day", 1500)
        remaining_quota = max(0, limit_rpd - daily_stats["requests"])
        
        # Calculate uptime
        uptime = int(time.time() - START_TIME)
        
        # Last request details
        last_req_ts = ""
        if self.tracker.history:
            last_req_ts = datetime.datetime.fromtimestamp(
                self.tracker.history[-1]["timestamp"]
            ).isoformat()
            
        # Extract recent requests history (last 20)
        recent_requests = []
        for r in reversed(self.tracker.history[-20:]):
            recent_requests.append({
                "timestamp": datetime.datetime.fromtimestamp(r["timestamp"]).isoformat(),
                "provider": r["provider"],
                "model": r["model"],
                "input_tokens": r["input_tokens"],
                "output_tokens": r["output_tokens"],
                "latency": round(r["latency"], 2),
                "success": r["success"],
                "error": r["error"],
                "is_retry": r["is_retry"],
                "prompt_profile": r.get("prompt_profile", {})
            })
            
        # Weekly history summary (last 7 days including today)
        weekly_history = []
        today = datetime.date.today()
        for i in range(6, -1, -1):
            d = today - datetime.timedelta(days=i)
            d_str = d.strftime("%Y-%m-%d")
            day_data = self.tracker.daily_history.get(d_str, {
                "requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "success": 0,
                "failure": 0
            })
            weekly_history.append({
                "date": d_str,
                "requests": day_data["requests"],
                "tokens": day_data["input_tokens"] + day_data["output_tokens"],
                "success": day_data["success"],
                "failure": day_data["failure"]
            })

        # Compute Prompt Profiler metrics
        successful_reqs = [r for r in self.tracker.history if r["success"]]
        
        avg_prompt_size = 0.0
        avg_response_size = 0.0
        avg_tokens_saved = 0.0
        pct_reduction = 0.0
        est_latency_improvement = 0.0
        
        total_baseline = 0
        total_actual = 0
        total_saved = 0
        
        for r in successful_reqs:
            profile = r.get("prompt_profile", {})
            actual = profile.get("total_prompt_tokens", r["input_tokens"])
            baseline = profile.get("baseline_tokens", r["input_tokens"])
            saved = max(0, baseline - actual)
            
            total_baseline += baseline
            total_actual += actual
            total_saved += saved
            
        if successful_reqs:
            num_reqs = len(successful_reqs)
            avg_prompt_size = total_actual / num_reqs
            avg_response_size = sum(r["output_tokens"] for r in successful_reqs) / num_reqs
            avg_tokens_saved = total_saved / num_reqs
            
            if total_baseline > 0:
                pct_reduction = (total_saved / total_baseline) * 100
                
            # Heuristic: 1ms latency improvement per token saved
            est_latency_improvement = avg_tokens_saved * 0.001

        # Largest prompts (top 5 sorted by total_prompt_tokens descending)
        sorted_by_size = sorted(
            self.tracker.history,
            key=lambda x: x.get("prompt_profile", {}).get("total_prompt_tokens", x["input_tokens"]),
            reverse=True
        )
        largest_prompts = []
        for r in sorted_by_size[:5]:
            profile = r.get("prompt_profile", {})
            largest_prompts.append({
                "timestamp": datetime.datetime.fromtimestamp(r["timestamp"]).isoformat(),
                "provider": r["provider"],
                "model": r["model"],
                "total_prompt_tokens": profile.get("total_prompt_tokens", r["input_tokens"]),
                "baseline_tokens": profile.get("baseline_tokens", r["input_tokens"]),
                "tokens_saved": max(0, profile.get("baseline_tokens", r["input_tokens"]) - profile.get("total_prompt_tokens", r["input_tokens"])),
                "prompt_profile": profile
            })

        # Compile model benchmarks dynamically
        try:
            from model_manager import model_manager
            supported_models = model_manager.get_supported_models()
        except Exception:
            supported_models = {}

        model_benchmarks = {}
        for m_id, m_profile in supported_models.items():
            stats = self.tracker.model_stats.get(m_id, {})
            reqs = stats.get("requests", 0)
            successes = stats.get("success_count", 0)
            
            avg_latency = stats.get("latency_sum", 0.0) / successes if successes > 0 else 0.0
            avg_prompt = stats.get("input_tokens", 0) / reqs if reqs > 0 else 0.0
            avg_response = stats.get("output_tokens", 0) / reqs if reqs > 0 else 0.0
            success_rate = (successes / reqs * 100) if reqs > 0 else 0.0
            
            # Tool calls success rate
            tool_attempted = stats.get("tool_calls_attempted", 0)
            tool_succeeded = stats.get("tool_calls_succeeded", 0)
            tool_success_rate = (tool_succeeded / tool_attempted * 100) if tool_attempted > 0 else 100.0
            
            model_benchmarks[m_id] = {
                "name": m_profile.name,
                "provider": m_profile.provider,
                "description": m_profile.description,
                "rpm": m_profile.rpm,
                "rpd": m_profile.rpd,
                "context_window": m_profile.context_window,
                "output_token_limit": m_profile.output_token_limit,
                "recommended_usage": m_profile.recommended_usage,
                "requests": reqs,
                "input_tokens": stats.get("input_tokens", 0),
                "output_tokens": stats.get("output_tokens", 0),
                "average_latency": round(avg_latency, 2),
                "average_prompt_tokens": round(avg_prompt, 1),
                "average_response_tokens": round(avg_response, 1),
                "success_rate": round(success_rate, 1),
                "tool_success_rate": round(tool_success_rate, 1),
                "tool_calls_attempted": tool_attempted,
                "tool_calls_succeeded": tool_succeeded,
                "error_count": stats.get("error_count", 0),
                "rate_limit_events": stats.get("rate_limit_events", 0),
                "recent_errors": stats.get("errors", [])
            }

        # Requests in the last 60 seconds
        now = time.time()
        requests_this_minute = len([r for r in self.tracker.history if now - r["timestamp"] < 60.0])

        # Rate limit events today
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        rate_limit_events_today = sum(
            self.tracker.model_stats.get(m, {}).get("rate_limit_events", 0)
            for m in self.tracker.model_stats
        )

        return {
            "current_provider": provider,
            "current_model": model,
            # --- Request counts ---
            "requests_today": daily_stats["requests"],
            "requests_session": self.statistics.session_requests,
            "requests_this_minute": requests_this_minute,
            "rate_limit_events_today": rate_limit_events_today,
            # --- Token usage ---
            "input_tokens_today": daily_stats["input_tokens"],
            "output_tokens_today": daily_stats["output_tokens"],
            "total_tokens_today": daily_stats["input_tokens"] + daily_stats["output_tokens"],
            "input_tokens_session": self.statistics.session_input_tokens,
            "output_tokens_session": self.statistics.session_output_tokens,
            "total_tokens_session": self.statistics.session_input_tokens + self.statistics.session_output_tokens,
            "input_tokens_cumulative": cumulative_stats["input_tokens"],
            "output_tokens_cumulative": cumulative_stats["output_tokens"],
            "total_tokens_cumulative": cumulative_stats["input_tokens"] + cumulative_stats["output_tokens"],
            # --- Latency / health ---
            "average_latency": round(self.statistics.get_avg_latency(), 2),
            "failed_requests": daily_stats["failure"],
            "failed_requests_session": self.statistics.session_failure,
            "retry_count": self.statistics.session_retries,
            "successful_requests": daily_stats["success"],
            "successful_requests_session": self.statistics.session_success,
            "last_request_timestamp": last_req_ts,
            "backend_uptime": uptime,
            "launcher_status": self.monitor.get_launcher_status(),
            # --- Quota (all values are ESTIMATED from local tracking) ---
            "remaining_quota": remaining_quota,
            "remaining_quota_estimated": True,  # Google AI Studio does not expose real-time quota
            # --- History ---
            "recent_requests": recent_requests,
            "weekly_history": weekly_history,
            # --- Prompt optimization metrics ---
            "average_prompt_size": round(avg_prompt_size, 1),
            "average_response_size": round(avg_response_size, 1),
            "average_tokens_saved": round(avg_tokens_saved, 1),
            "percentage_reduction": round(pct_reduction, 1),
            "estimated_latency_improvement": round(est_latency_improvement, 3),
            "largest_prompts": largest_prompts,
            # --- Model benchmarks ---
            "model_benchmarks": model_benchmarks
        }


# Global ResourceManager singleton
resource_manager = ResourceManager()


def estimate_tokens(text: str) -> int:
    """Simple token count estimator based on character length."""
    return len(text) // 4


def is_rate_limit_exception(e: Exception) -> bool:
    """Helper to detect rate limit exceptions from common AI client libraries."""
    msg = str(e).lower()
    return "429" in msg or "rate limit" in msg or "resourceexhausted" in msg or "quota" in msg


def execute_llm_request_with_rate_limits(
    provider_name: str,
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    request_type: str = "plan",
    prompt_profile: Optional[Any] = None,
    model_profile: Optional[Any] = None,
    ctx: Optional[Any] = None
) -> str:
    """
    Unified gateway function for executing LLM requests.
    Handles proactive limit checks, sleep delay queueing, token estimation,
    exponential retry backoffs for rate limits, latency tracking, and updates stats.
    """
    try:
        from main import log_message
    except ImportError:
        def log_message(level, msg):
            print(f"[{level}] {msg}")

    req_id = ctx.prefix() if ctx else ""

    # Resolve provider and model from ModelProfile if passed
    if model_profile:
        model_name = model_profile.model_id
        provider_name = model_profile.provider

    # Estimate input tokens for rate limiting checks
    estimated_input = estimate_tokens(system_prompt) + estimate_tokens(user_prompt)
    
    # 1. Proactive Rate Limiting Delay Queue
    delay_cycles = 0
    while True:
        limit_status = resource_manager.limiter.check_limits(provider_name, estimated_input)
        if limit_status == "daily_quota_exceeded":
            log_message("WARNING", f"{req_id} Daily API Quota limit exceeded for provider '{provider_name}'. Blocking request.")
            raise Exception(f"Daily request quota limit exceeded for provider '{provider_name}'.")

        if limit_status in ["rpm_exceeded", "tpm_exceeded"]:
            wait_sec = resource_manager.limiter.get_proactive_wait_time(provider_name, estimated_input)
            if wait_sec > 0.0:
                log_message("WARNING", f"{req_id} Proactive rate limit triggered ({limit_status}). Delaying request by {wait_sec:.2f}s...")
                resource_manager.record_rate_limit_event(model_name)
                time.sleep(wait_sec)
                delay_cycles += 1
                if delay_cycles > 5:  # safety breakout
                    break
                continue
        break

    # Initialize Provider
    try:
        provider = get_provider(provider_name, model_name)
    except Exception as init_err:
        log_message("ERROR", f"{req_id} LLM Provider initialization failed: {init_err}")
        raise init_err

    # 2. Run LLM call with reactive retries on 429 Rate Limits
    max_retries = 3
    backoff = 2.0
    start_time = time.time()
    
    for attempt in range(max_retries + 1):
        is_retry = (attempt > 0)
        try:
            # Reload environment variables in case key was updated dynamically
            load_dotenv(override=True)

            response_text = provider.generate(system_prompt, user_prompt, ctx=ctx)
            latency = time.time() - start_time
            
            # Extract actual or estimate tokens
            input_tokens = estimated_input
            output_tokens = estimate_tokens(response_text)
            
            # If the provider is Gemini, check if it returned token usage in response
            # Since GeminiProvider returns response.text (a string), we don't have usage_metadata on it directly,
            # but we can look for it in the provider or use our estimate.
            # To be robust, let's check if the provider object has recorded usage metadata
            # or if we can extract it.
            # We will also make GeminiProvider set a `last_usage_metadata` attribute when it completes.
            if hasattr(provider, "last_usage_metadata") and provider.last_usage_metadata:
                input_tokens = provider.last_usage_metadata.get("prompt_tokens", input_tokens)
                output_tokens = provider.last_usage_metadata.get("completion_tokens", output_tokens)

            # Update prompt_profile total tokens to match actual parsed input tokens if we have it
            if prompt_profile:
                if hasattr(prompt_profile, "total_prompt_tokens"):
                    prompt_profile.total_prompt_tokens = input_tokens
                elif isinstance(prompt_profile, dict):
                    prompt_profile["total_prompt_tokens"] = input_tokens

            # Record successful request
            resource_manager.tracker.record_request(
                provider=provider_name,
                model=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency=latency,
                success=True,
                is_retry=is_retry,
                prompt_profile=prompt_profile,
                request_id=ctx.request_id if ctx else None
            )
            resource_manager.statistics.record_session_request(
                success=True,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency=latency,
                is_retry=is_retry
            )
            
            return response_text
            
        except Exception as e:
            latency = time.time() - start_time

            # If it's a rate limit exception, and we still have retries remaining, sleep and retry
            if is_rate_limit_exception(e) and attempt < max_retries:
                log_message("WARNING", f"{req_id} LLM rate limit (429) hit on attempt {attempt + 1}. Retrying in {backoff}s... Error: {e}")
                resource_manager.record_rate_limit_event(model_name)
                time.sleep(backoff)
                backoff *= 2.0
                continue

            # Log and record failed request
            log_message("ERROR", f"{req_id} LLM request failed after {latency:.2f}s [{request_type}]: {type(e).__name__}: {e}")
            
            # Record failed request
            resource_manager.tracker.record_request(
                provider=provider_name,
                model=model_name,
                input_tokens=estimated_input,
                output_tokens=0,
                latency=latency,
                success=False,
                error_msg=str(e),
                is_retry=is_retry,
                prompt_profile=prompt_profile,
                request_id=ctx.request_id if ctx else None
            )
            resource_manager.statistics.record_session_request(
                success=False,
                input_tokens=estimated_input,
                output_tokens=0,
                latency=latency,
                is_retry=is_retry
            )
            raise e
