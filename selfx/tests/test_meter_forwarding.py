from copy import deepcopy
from agent.graph import AgentDeps, build_graph, run_cycle
from agent.memory import MemoryStore
from agent.schemas import DecisionOutput, ReflectionOutput
from tests.test_graph import FakeLLM


def run_meter(has_output):
    match={"in_port":1,"eth_type":2048,"ipv4_dst":"10.0.0.8"}
    base={"switches":{"1":{"flows":[{"match":match,"byte_count":0,"priority":100,"table_id":0,
                                          "actions":["OUTPUT:2"] if has_output else []}],
                                  "ports":[{"port_no":2,"tx_bytes":0,"tx_packets":0}]}}}
    count=[0]
    def snapshot():
        count[0]+=1
        state=deepcopy(base)
        state["switches"]["1"]["flows"][0]["byte_count"]=500000*count[0]
        state["switches"]["1"]["ports"][0]["tx_bytes"]=500000*count[0]
        return state
    installed=[]
    decision=DecisionOutput(action="rate_limit",target_dpid=1,target_flow_match=match,rate_limit_kbps=720,rationale="10 percent reduction")
    deps=AgentDeps(llm=FakeLLM([decision],[ReflectionOutput(reflection="Measured intervention")]),
                   memory=MemoryStore(enabled=False),get_state_fn=snapshot,
                   add_flow_fn=lambda *args,**kw:installed.append((args,kw)),
                   add_meter_fn=lambda *args,**kw:None,wait_fn=lambda _:None,latency_fn=lambda:10.)
    return run_cycle(build_graph(deps),0,base),installed


def test_meter_preserves_forwarding_and_expires():
    result,installed=run_meter(True)
    assert result["installed_action"]=="rate_limit"
    actions=installed[0][0][2]
    assert actions[0]["type"]=="METER" and actions[1]=={"type":"OUTPUT","port":2}
    assert installed[0][1]["hard_timeout"]==5


def test_missing_forwarding_is_vetoed_instead_of_installing_drop_rule():
    result,installed=run_meter(False)
    assert result["installed_action"]=="no_op" and installed==[]
    assert "forwarding" in result["safety_result"]["reason"]
