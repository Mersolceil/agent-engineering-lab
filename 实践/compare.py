"""相同两个资料分片、相同策略替身、相同调用上限；仅验证并发与隔离。"""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
from lab import ScriptedModel, new_state, run


class DelayedModel(ScriptedModel):
    def query(self, state):
        time.sleep(.02)  # 注入固定服务等待，不能解释为真实 API 延迟
        return super().query(state)


def worker(topic):
    return run(new_state(topic, max_steps=2), DelayedModel())


def experiment(parallel):
    t = time.perf_counter()
    topics = ['alpha','beta']
    if parallel:
        with ThreadPoolExecutor(max_workers=2) as pool:
            states = list(pool.map(worker, topics))
    else:
        states = [worker(topic) for topic in topics]
    # 确定性汇总器无模型调用，分别记录传输消息字节
    merged = {s['topic']: s['answer'] for s in states}
    return {'mode': 'two_workers' if parallel else 'sequential_isolated_loops',
            'elapsed_s': time.perf_counter()-t,
            'model_calls': sum(s['steps'] for s in states),
            'tool_calls': sum(sum(m['role']=='tool' for m in s['messages']) for s in states),
            'success': all(s['status']=='success' for s in states),
            'coordinator_model_calls': 0,
            'worker_result_bytes': len(json.dumps(merged,ensure_ascii=False).encode()),
            'model_tokens': None,
            'answers': merged}


if __name__=='__main__':
    results = [experiment(p) for _ in range(5) for p in (False,True)]
    Path('results/comparison.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    print(json.dumps(results, ensure_ascii=False, indent=2))
