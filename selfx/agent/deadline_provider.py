"""Cancellable process isolation for the control path's provider wait.

Parent pacing, startup, IPC, cancellation and join are inside the measured call.
Killing the local client cannot cancel generation already received by the server.
"""
import multiprocessing as mp
import os,time
from agent.providers import ProviderError


def request_worker(connection,provider,model,messages):
    # Only the parent paces. The child inherits credentials, never serializes them.
    os.environ['GEMINI_REQUEST_GAP_SEC']='0'
    os.environ['OPENROUTER_REQUEST_GAP_SEC']='0'
    from agent.providers import RestLLM
    from agent.fast_control import ActionChoice
    llm=RestLLM(provider,model,profile='compact')
    try:
        while messages is not None:
            before=len(llm.audit);llm.failures.clear()
            connection.send({'event':'request_started'})
            try:
                result=llm.with_structured_output(ActionChoice).invoke(messages)
                connection.send({'event':'result','choice':result.model_dump(),'audit':llm.audit[before:]})
            except Exception:
                connection.send({'event':'error','audit':llm.audit[before:],'code':'provider_unavailable'})
            try:messages=connection.recv()
            except EOFError:break
    finally:
        if llm.session:llm.session.close()
        connection.close()


class DeadlineProvider:
    last_started={}
    def __init__(self,provider,model=None,budget_seconds=3.8,worker=request_worker):
        self.provider=provider;self.model=model;self.budget_seconds=budget_seconds
        self.worker=worker;self.audit=[];self.last_proposal=None
        self.process=None;self.connection=None

    def close(self):
        if self.process is not None:
            if self.process.is_alive():self.process.terminate()
            self.process.join(timeout=.15)
            if self.process.is_alive():self.process.kill();self.process.join(timeout=.05)
            self.process=None
        if self.connection is not None:self.connection.close();self.connection=None

    def choose(self,messages):
        started=time.perf_counter();deadline=started+self.budget_seconds
        self.last_proposal=None
        gap=float(os.environ.get('GEMINI_REQUEST_GAP_SEC' if self.provider=='gemini' else 'OPENROUTER_REQUEST_GAP_SEC','4.2' if self.provider=='gemini' else '3.1'))
        delay=max(0,gap-(time.monotonic()-self.last_started.get(self.provider,0)))
        # Preserve at least 1 second for transport and 0.25 seconds for cleanup.
        if delay>0 and delay>self.budget_seconds-1.25:
            self.audit.append(dict(provider=self.provider,status='deferred',error_code='pacing_admission',request_started=False,elapsed_ms=1000*(time.perf_counter()-started),pacing_ms=0))
            raise ProviderError('pacing_admission')
        if delay:time.sleep(delay)
        pacing_ms=1000*(time.perf_counter()-started)
        began=False;result=None
        try:
            if self.process is None or not self.process.is_alive():
                self.close();parent,child=mp.get_context('spawn').Pipe()
                self.process=mp.get_context('spawn').Process(target=self.worker,args=(child,self.provider,self.model,messages),daemon=True)
                self.connection=parent;self.process.start();child.close()
            else:self.connection.send(messages)
            process=self.process;parent=self.connection
            while time.perf_counter()<deadline-.2:
                if parent.poll(max(0,min(.05,deadline-.2-time.perf_counter()))):
                    try:event=parent.recv()
                    except EOFError:break
                    if event['event']=='request_started':
                        began=True;self.last_started[self.provider]=time.monotonic()
                    else:result=event;break
                if not process.is_alive() and not parent.poll():break
        finally:
            # A successful/error response leaves an idle worker, never an in-flight
            # background request. Reuse preserves its HTTP pool; timeout kills it.
            if result is None:self.close()
        elapsed=1000*(time.perf_counter()-started)
        audit=(result or {}).get('audit',[])
        if audit:
            for record in audit:record.update(request_started=began,worker_elapsed_ms=elapsed,pacing_ms=pacing_ms,deadline_budget_ms=self.budget_seconds*1000)
            self.audit.extend(audit)
        else:
            self.audit.append(dict(provider=self.provider,requested_model=self.model,status='deadline_timeout' if began else 'startup_timeout',error_code='local_deadline',request_started=began,elapsed_ms=elapsed,pacing_ms=pacing_ms,deadline_budget_ms=self.budget_seconds*1000))
        if result and result['event']=='result':
            self.last_proposal=result['choice'];return result['choice']
        raise ProviderError((result or {}).get('code','local_deadline'))
