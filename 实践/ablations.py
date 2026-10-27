"""合成机制反例：测规则/账本，不冒充真实模型架构效果。"""
import json
from pathlib import Path
from lab import new_state, run, ScriptedModel


def main():
    rows=[]
    for scenario in ['normal','badargs','transient','loop','early']:
        for budget in [1,2,4]:
            r=run(new_state('alpha',scenario,max_steps=budget),ScriptedModel(scenario))
            rows.append({'comparison':'retry_budget','scenario':scenario,'budget':budget,
                         'status':r['status'],'model_calls':r['steps'],
                         'tool_calls':sum(m['role']=='tool' for m in r['messages'])})
    # 同样字符上限，原始按顺序截断会把任务约束挤掉；无模型质量主张。
    messages=[('constraint','只读；禁止发送'),('noise','无关日志'*100),('evidence','alpha:林')]
    full='\n'.join(text for _,text in messages)[:60]
    selected='\n'.join(text for kind,text in messages if kind!='noise')[:60]
    rows.append({'comparison':'context_selection','budget_chars':60,
                 'raw_has_evidence':'alpha:林' in full,
                 'selected_has_evidence':'alpha:林' in selected,
                 'raw_chars':len(full),'selected_chars':len(selected)})
    memories=[{'fact':'pytest','scope':'old_repo','valid':True},
              {'fact':'unittest','scope':'current_repo','valid':True},
              {'fact':'nose','scope':'current_repo','valid':False}]
    naive=memories[0]['fact']
    filtered=next(m['fact'] for m in memories if m['scope']=='current_repo' and m['valid'])
    rows.append({'comparison':'memory_scope','gold':'unittest','naive':naive,
                 'scope_filtered':filtered,'no_memory':'unknown'})
    out = Path('results/generated'); out.mkdir(parents=True, exist_ok=True)
    (out/'ablations.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    print(json.dumps(rows,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
