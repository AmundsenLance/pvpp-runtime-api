"""Runtime 2.2 Phase-3 observation admission and governed current-view service."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib, json
from typing import Any, Mapping
from .models import SemanticId
from .store import SQLiteSupervisoryStore, ConcurrencyConflict

@dataclass(frozen=True, slots=True)
class SourceRegistration:
    source_registration_id:str; source_id:str; evidence_roles:tuple[str,...]; fact_kinds:tuple[str,...]
    subject_scope:tuple[str,...]; configuration_scope:tuple[str,...]; permitted_uses:tuple[str,...]
    attestation_method:str; valid_from:str|None; valid_until:str|None; status:str; registration_authority:str; version:int

@dataclass(frozen=True, slots=True)
class ExternalObservation:
    observation_id:str; source_id:str; fact_kind:str; fact_id:str; subject_id:str; configuration_id:str
    value:Any; confidence:float|None; effective_at:str; observed_at:str; received_at:str; payload:Mapping[str,Any]

@dataclass(frozen=True, slots=True)
class ObservationAdmissionRecord:
    admission_id:str; observation_id:str; source_registration_id:str|None; disposition:str; reason:str
    authoritative:bool; applicable:bool; permitted:bool; temporally_valid:bool; assessed_at:str

@dataclass(frozen=True, slots=True)
class GovernedFactView:
    fact_kind:str; fact_id:str; subject_id:str; configuration_id:str; state:str; value:Any
    effective_at:str; observation_ids:tuple[str,...]; version:int

@dataclass(frozen=True, slots=True)
class AdmittedFactChange:
    change_id:str; subject_id:str; fact_kind:str; changed_fact_ids:tuple[str,...]; prior_view_version:int|None; new_view_version:int
    observation_ids:tuple[str,...]; admission_ids:tuple[str,...]; committed_at:str

class ObservationService:
    def __init__(self, store:SQLiteSupervisoryStore):
        self.store=store; self._c=store._conn; self._lock=store._lock
        with self._lock:
            self._c.executescript('''
            CREATE TABLE IF NOT EXISTS source_registrations(registration_id TEXT PRIMARY KEY,source_id TEXT NOT NULL,version INTEGER NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL,UNIQUE(source_id,version));
            CREATE INDEX IF NOT EXISTS idx_source_current ON source_registrations(source_id,status,version);
            CREATE TABLE IF NOT EXISTS observations(observation_id TEXT PRIMARY KEY,digest TEXT NOT NULL,payload TEXT NOT NULL,received_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS observation_admissions(admission_id TEXT PRIMARY KEY,observation_id TEXT NOT NULL,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS governed_fact_views(fact_key TEXT PRIMARY KEY,version INTEGER NOT NULL,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS admitted_fact_changes(change_id TEXT PRIMARY KEY,fact_key TEXT NOT NULL,payload TEXT NOT NULL);
            ''')
    def register_source(self,r:SourceRegistration, *, authority_proof=None)->None:
        if r.status not in {'current','revoked','superseded','limited'}: raise ValueError('invalid source status')
        config = r.configuration_scope[0] if len(r.configuration_scope)==1 else None
        self.store.require_registration_authority(authority_id=r.registration_authority, role='source_registration', configuration_id=config, authority_proof=authority_proof)
        p=json.dumps(r.__dict__ if hasattr(r,'__dict__') else {f:getattr(r,f) for f in r.__dataclass_fields__},sort_keys=True,separators=(',',':'))
        with self._lock:
            self._c.execute('INSERT INTO source_registrations VALUES(?,?,?,?,?)',(r.source_registration_id,r.source_id,r.version,p,r.status))
    def current_registration(self,source_id:str)->SourceRegistration|None:
        row=self._c.execute("SELECT payload FROM source_registrations WHERE source_id=? ORDER BY version DESC LIMIT 1",(source_id,)).fetchone()
        if not row:return None
        d=json.loads(row['payload']);
        for k in ('evidence_roles','fact_kinds','subject_scope','configuration_scope','permitted_uses'): d[k]=tuple(d[k])
        return SourceRegistration(**d)
    def submit_observation(self,o:ExternalObservation)->ExternalObservation:
        d={f:getattr(o,f) for f in o.__dataclass_fields__}; enc=json.dumps(d,sort_keys=True,separators=(',',':')); dig=hashlib.sha256(enc.encode()).hexdigest()
        with self._lock:
            row=self._c.execute('SELECT digest FROM observations WHERE observation_id=?',(o.observation_id,)).fetchone()
            if row:
                if row['digest']!=dig: raise ConcurrencyConflict('identity_conflict: observation_id reused with changed content')
                return o
            self._c.execute('INSERT INTO observations VALUES(?,?,?,?)',(o.observation_id,dig,enc,o.received_at))
        self.store.record_supervisory_operation('observation_submitted',occurred_at=o.received_at,configuration_id=o.configuration_id,subject_id=o.subject_id,payload={'initiating_event_id':o.observation_id,'operation':'submit_observation','result_ref':o.observation_id,'invariant_status':'accepted','error':None})
        return o
    def assess_observation(self,o:ExternalObservation,*,assessed_at:str,permitted_use:str='governance')->ObservationAdmissionRecord:
        r=self.current_registration(o.source_id)
        auth=bool(r and r.status=='current')
        applicable=bool(r and o.fact_kind in r.fact_kinds and (not r.subject_scope or o.subject_id in r.subject_scope) and (not r.configuration_scope or o.configuration_id in r.configuration_scope))
        permitted=bool(r and permitted_use in r.permitted_uses and 'observation' in r.evidence_roles)
        temporal=bool(r and (r.valid_from is None or o.effective_at>=r.valid_from) and (r.valid_until is None or o.effective_at<=r.valid_until))
        ok=auth and applicable and permitted and temporal
        reason='admissible' if ok else ('source_not_current' if not auth else 'scope_or_use_or_time_invalid')
        a=ObservationAdmissionRecord(SemanticId.new('adm').value,o.observation_id,r.source_registration_id if r else None,'admissible' if ok else 'retained_noncurrent',reason,auth,applicable,permitted,temporal,assessed_at)
        enc=json.dumps({f:getattr(a,f) for f in a.__dataclass_fields__},sort_keys=True,separators=(',',':'))
        with self._lock:self._c.execute('INSERT INTO observation_admissions VALUES(?,?,?)',(a.admission_id,a.observation_id,enc))
        self.store.record_supervisory_operation('observation_assessed',occurred_at=assessed_at,configuration_id=o.configuration_id,subject_id=o.subject_id,payload={'initiating_event_id':o.observation_id,'operation':'assess_observation','authority_source':a.source_registration_id,'result_ref':a.admission_id,'invariant_status':a.disposition,'error':None})
        return a
    def _fact_key(self,o): return f'{o.configuration_id}|{o.subject_id}|{o.fact_kind}|{o.fact_id}'
    def read_current_fact_view(self,*,configuration_id:str,subject_id:str,fact_kind:str,fact_id:str)->GovernedFactView|None:
        key=f'{configuration_id}|{subject_id}|{fact_kind}|{fact_id}'; row=self._c.execute('SELECT payload FROM governed_fact_views WHERE fact_key=?',(key,)).fetchone()
        if not row:return None
        d=json.loads(row['payload']); d['observation_ids']=tuple(d['observation_ids']); return GovernedFactView(**d)
    def commit_admission_change(self,o:ExternalObservation,a:ObservationAdmissionRecord,*,committed_at:str)->AdmittedFactChange|None:
        if a.observation_id!=o.observation_id: raise ValueError('admission/observation mismatch')
        if a.disposition!='admissible': return None
        key=self._fact_key(o)
        with self._lock:
            try:
                self._c.execute('BEGIN IMMEDIATE')
                row=self._c.execute('SELECT version,payload FROM governed_fact_views WHERE fact_key=?',(key,)).fetchone()
                prior=None; changed=False
                if row is None:
                    state='current'; value=o.value; obs=(o.observation_id,); ver=1; changed=True
                else:
                    prior=row['version']; d=json.loads(row['payload']); cur_eff=d['effective_at']; cur_val=d['value']; cur_obs=tuple(d['observation_ids'])
                    if o.effective_at < cur_eff:
                        self._c.execute('COMMIT'); return None
                    if o.effective_at==cur_eff and o.value!=cur_val:
                        state='unresolved'; value=None; obs=tuple(dict.fromkeys(cur_obs+(o.observation_id,))); ver=prior+1; changed=True
                    elif o.effective_at>cur_eff or (d['state']=='unresolved' and o.effective_at>cur_eff):
                        state='current'; value=o.value; obs=(o.observation_id,); ver=prior+1; changed=True
                    elif o.observation_id in cur_obs or o.value==cur_val:
                        self._c.execute('COMMIT'); return None
                    else:
                        self._c.execute('COMMIT'); return None
                view=GovernedFactView(o.fact_kind,o.fact_id,o.subject_id,o.configuration_id,state,value,o.effective_at,obs,ver)
                venc=json.dumps({f:getattr(view,f) for f in view.__dataclass_fields__},sort_keys=True,separators=(',',':'))
                self._c.execute('INSERT INTO governed_fact_views VALUES(?,?,?) ON CONFLICT(fact_key) DO UPDATE SET version=excluded.version,payload=excluded.payload',(key,ver,venc))
                ch=AdmittedFactChange(SemanticId.new('chg').value,o.subject_id,o.fact_kind,(o.fact_id,),prior,ver,obs,(a.admission_id,),committed_at)
                cenc=json.dumps({f:getattr(ch,f) for f in ch.__dataclass_fields__},sort_keys=True,separators=(',',':'))
                self._c.execute('INSERT INTO admitted_fact_changes VALUES(?,?,?)',(ch.change_id,key,cenc)); self._c.execute('COMMIT')
                self.store.record_supervisory_operation('fact_change_committed',occurred_at=committed_at,configuration_id=o.configuration_id,subject_id=o.subject_id,payload={'initiating_event_id':o.observation_id,'operation':'commit_admission_change','state_version_before':prior,'state_version_after':ver,'authority_source':a.source_registration_id,'result_ref':ch.change_id,'invariant_status':'committed','error':None})
                return ch
            except Exception:
                if self._c.in_transaction:self._c.execute('ROLLBACK')
                raise
    def observation_count(self)->int:
        return self._c.execute('SELECT count(*) n FROM observations').fetchone()['n']
