"""计量必须显式区分实测 usage、未知费用和合成数据。"""
import argparse
import json
import math
from pathlib import Path
import statistics


def cost(usage, rates):
    # rates 是每百万 token 单价，不自带可能过期的模型价格。
    if not usage or rates is None:
        return None
    if any(not isinstance(rates[k], (int,float)) or not math.isfinite(rates[k])
           or rates[k] < 0 for k in ('input','cached_input','output')):
        raise ValueError('rates must be finite and nonnegative')
    input_n, output_n = usage['input_tokens'], usage['output_tokens']
    cached = usage.get('input_tokens_details', {}).get('cached_tokens', 0)
    if not (0 <= cached <= input_n and output_n >= 0):
        raise ValueError('invalid usage')
    # Responses 的 reasoning_tokens 属于 output_tokens 子集，不能再相加。
    return ((input_n-cached)*rates['input'] + cached*rates['cached_input']
            + output_n*rates['output'])/1_000_000


def summarize(runs, rates=None):
    n = len(runs)
    success = sum(r['status'] == 'success' for r in runs)
    all_usage = [u for r in runs for u in r['usage']]
    costs = [cost(u, rates) for u in all_usage]
    total_cost = sum(costs) if costs and all(c is not None for c in costs) else None
    extras = [r.get('non_token_cost') for r in runs]
    extras_total = sum(extras) if n and all(x is not None for x in extras) else None
    full_cost = total_cost + extras_total if total_cost is not None and extras_total is not None else None
    p = success/n if n else 0
    z = 1.96  # 近似 Wilson 区间；非独立样本时不可当总体置信区间
    den = 1+z*z/n if n else 1
    mid = (p+z*z/(2*n))/den if n else 0
    half = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den if n else 0
    times = sorted(r['elapsed_s'] for r in runs)
    return {'n': n, 'successes': success, 'success_rate': p,
            'wilson95_if_iid': [mid-half, mid+half] if n else None,
            'latency_mean_s': statistics.mean(times) if times else None,
            'latency_p95_s': times[max(0, math.ceil(.95*n)-1)] if n else None,
            'model_calls': len(all_usage),
            'tool_calls': sum(sum(m['role']=='tool' for m in r['messages']) for r in runs),
            'input_tokens': sum(u['input_tokens'] for u in all_usage) if all_usage and all(all_usage) else None,
            'output_tokens': sum(u['output_tokens'] for u in all_usage) if all_usage and all(all_usage) else None,
            'cost': total_cost,  # 兼容字段：仅 token 费用
            'token_cost': total_cost,
            'non_token_cost': extras_total,
            'total_cost_all_categories': full_cost,
            'total_cost_per_success': full_cost/success if full_cost is not None and success else None,
            # 所有失败/重试的费用进入分子
            'cost_per_success': total_cost/success if total_cost is not None and success else None,
            'retry_count': sum(r['transient_retries'] for r in runs),
            'timings_sum': {k: sum(r['timings'][k] for r in runs)
                            for k in ('model_s','tool_s','checkpoint_s')}}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('runs')
    p.add_argument('--rates', help='带 input,cached_input,output 的每百万 token 价格 JSON')
    a = p.parse_args()
    runs = json.loads(Path(a.runs).read_text())
    rates = json.loads(Path(a.rates).read_text()) if a.rates else None
    print(json.dumps(summarize(runs, rates), indent=2, ensure_ascii=False))
