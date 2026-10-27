import json
from pathlib import Path
import platform
from lab import new_state, run, ScriptedModel
from metrics import summarize

# gold 标签来自独立任务规范；success 意味着完成目标，不是测试断言通过。
TASKS = [
    ('lookup_alpha','alpha','normal','success'),
    ('lookup_beta','beta','normal','success'),
    ('untrusted_text','gamma','normal','success'),
    ('repair_arguments','alpha','badargs','success'),
    ('read_timeout','alpha','transient','success'),
    ('no_evidence','alpha','early','rejected_final'),
    ('repeated_action','alpha','loop','repeat_limit'),
    ('missing_document','missing','normal','rejected_final'),
]


def main():
    out = Path('results'); out.mkdir(exist_ok=True)
    runs = []
    for repeat in range(5):
        for task_id, topic, scenario, expected in TASKS:
            state = run(new_state(topic, scenario), ScriptedModel(scenario))
            state.update(task_id=task_id, repeat=repeat, expected=expected,
                         contract_pass=state['status']==expected)
            runs.append(state)
    (out/'runs.json').write_text(json.dumps(runs, ensure_ascii=False, indent=2))
    summary = {'experiment': 'runtime-contracts-v1', 'python': platform.python_version(),
               'model': 'scripted-v1', 'real_model_executed': False,
               'repetitions': 5, 'unique_tasks': len(TASKS),
               'contract_passes': sum(r['contract_pass'] for r in runs),
               'per_repeat_success_rates': [sum(r['status']=='success' for r in runs
                    if r['repeat']==i)/len(TASKS) for i in range(5)],
               'metrics': summarize(runs)}
    # 确定性重复不满足独立随机抽样，禁止据此给能力置信区间。
    summary['metrics']['wilson95_if_iid'] = None
    summary['iid_assumption_satisfied'] = False
    (out/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not all(r['contract_pass'] for r in runs):
        raise SystemExit(1)


if __name__=='__main__':
    main()
