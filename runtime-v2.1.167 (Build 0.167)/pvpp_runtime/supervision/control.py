"""Runtime 2.2 supervisory ownership, fencing, control and enforcement."""
from __future__ import annotations
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Mapping
import re
from .models import SemanticId, SupervisoryOwnershipRecord, AdapterRegistration, ExecutionControlRequest, ControlAttemptRecord, EnforcementRecord
from .store import SQLiteSupervisoryStore, ConcurrencyConflict
from .dependency import DependencyService
from .continuation import ContinuationService
from .bridge import CanonicalRuntimeBridge

class StaleOwner(ConcurrencyConflict): pass
class AdapterUnregistered(RuntimeError): pass
class ControlMappingWidened(RuntimeError): pass
class TargetScopeViolation(RuntimeError): pass
class EvidenceUnverified(RuntimeError): pass

class ControlService:
    OUTCOMES={'accepted','completed','rejected','too_late','timed_out','unknown'}
    CONTROL_ORDER={'hold':0,'pause':1,'cancel':2,'reauthorization_required':2,'terminate':3}
    SEMANTIC_CONTROLS=frozenset(CONTROL_ORDER)
    POSTURE_ALLOWED_CONTROLS={
        'continue':frozenset(),
        'reauthorization_required':frozenset({'hold','pause','cancel','reauthorization_required'}),
        'abort_return':frozenset(SEMANTIC_CONTROLS),
        'emergency_return':frozenset(SEMANTIC_CONTROLS),
        'indeterminate':frozenset({'hold','pause','reauthorization_required'}),
    }
    def __init__(self,store:SQLiteSupervisoryStore,dependencies:DependencyService,continuation:ContinuationService,bridge:CanonicalRuntimeBridge):
        self.store=store; self.dependencies=dependencies; self.continuation=continuation; self.bridge=bridge
    def register_owner_authority(self,*,owner_id,configuration_id,registration_authority,registered_at,authority_proof=None):
        self.store.register_supervisory_owner_authority(owner_id=owner_id,configuration_id=configuration_id,registration_authority=registration_authority,registered_at=registered_at,authority_proof=authority_proof)
    def register_supervisory_owner(self,*,owner_id,configuration_id,registration_authority,registered_at,authority_proof=None):
        return self.register_owner_authority(owner_id=owner_id,configuration_id=configuration_id,registration_authority=registration_authority,registered_at=registered_at,authority_proof=authority_proof)
    def acquire_ownership(self,*,active_execution_id,owner_id,acquired_at,expires_at=None):
        if not owner_id: raise ValueError('owner_id required')
        acquired=self._parse_time(acquired_at)
        if acquired is None: raise ValueError('invalid acquired_at timestamp')
        if expires_at is not None:
            expires=self._parse_time(expires_at)
            if expires is None: raise ValueError('invalid expires_at timestamp')
            if expires <= self.store.now(): raise ValueError('ownership lease already expired')
            if expires <= acquired: raise ValueError('ownership lease expires before acquisition')
        return SupervisoryOwnershipRecord(**self.store.acquire_supervisory_ownership(active_execution_id=active_execution_id,owner_id=owner_id,acquired_at=acquired_at,expires_at=expires_at))
    @staticmethod
    def _parse_time(v):
        if not v:return None
        try:
            dt=datetime.fromisoformat(str(v).replace('Z','+00:00'))
            if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:return None
    def _owner(self,active_execution_id,owner_id,owner_fence,*,at_time=None):
        raw=self.store.current_supervisory_ownership(active_execution_id); rec=self.store.get_active_execution(active_execution_id)
        if raw is None or raw['status']!='current' or raw['owner_id']!=owner_id or raw['owner_fence']!=owner_fence:raise StaleOwner('stale_owner')
        if rec is None or not self.store.supervisory_owner_authorized(owner_id=owner_id,configuration_id=rec.configuration_id):raise StaleOwner('stale_owner: owner authority unavailable')
        if at_time is not None and self._parse_time(at_time) is None:
            raise ValueError('invalid consequential operation timestamp')
        if raw.get('expires_at'):
            exp=self._parse_time(raw['expires_at']); now=self.store.now()
            if exp is None or now>=exp:raise StaleOwner('stale_owner: expired')
        return SupervisoryOwnershipRecord(**raw)
    @staticmethod
    def _valid_namespace(ns):
        return bool(ns and len(ns)>=2 and ns[-1] in {':','/','#'} and ns[:-1].replace('-','').replace('_','').isalnum())
    @staticmethod
    def _valid_target_suffix(suffix):
        return bool(suffix and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]*", suffix) and '..' not in suffix and '*' not in suffix and '/' not in suffix and '\\' not in suffix and not any(ch.isspace() for ch in suffix))
    @classmethod
    def _valid_target_handle(cls,target):
        if not isinstance(target,str): return False
        m=re.fullmatch(r"([A-Za-z0-9_-]{1,64}[:/#])([A-Za-z0-9][A-Za-z0-9._:-]{0,127})",target)
        return bool(m and cls._valid_target_suffix(m.group(2)))
    def register_adapter(self,*,adapter_id,configuration_id,target_handle_namespace,supported_semantic_controls,command_mapping:Mapping[str,str],controller_attestation_method,control_region_evidence_method,registration_authority,registered_at,vendor_command_mapping:Mapping[str,str]|None=None,authority_proof=None):
        if not registration_authority:raise ValueError('registration_authority required')
        self.store.require_registration_authority(authority_id=registration_authority, role='adapter_registration', configuration_id=configuration_id, authority_proof=authority_proof)
        if not self._valid_namespace(target_handle_namespace):raise TargetScopeViolation('target_scope_violation: namespace must be structured and exact')
        controls=tuple(dict.fromkeys(supported_semantic_controls))
        vendor_map=dict(vendor_command_mapping or {c:c for c in controls})
        if not controls:raise ValueError('supported_semantic_controls required')
        for c in controls:
            if c not in self.SEMANTIC_CONTROLS:raise ValueError(f'unsupported semantic control: {c}')
            mapped=command_mapping.get(c)
            if mapped is None:raise ValueError(f'missing mapping for {c}')
            if mapped not in self.SEMANTIC_CONTROLS:raise ControlMappingWidened('control_mapping_widened: mapped command outside closed vocabulary')
            if self.CONTROL_ORDER[mapped]>self.CONTROL_ORDER[c]:raise ControlMappingWidened('control_mapping_widened')
            vendor=vendor_map.get(c)
            if not isinstance(vendor,str) or not vendor.strip(): raise ValueError(f'missing vendor command binding for {c}')
        reg=AdapterRegistration(SemanticId.new('adapter').value,adapter_id,configuration_id,target_handle_namespace,controls,dict(command_mapping),vendor_map,controller_attestation_method,control_region_evidence_method,'current',1,registration_authority,registered_at)
        self.store.phase6_put('adapter_registrations','adapter_registration_id',reg.adapter_registration_id,asdict(reg),{'adapter_id':adapter_id,'configuration_id':configuration_id,'status':'current','version':1}); return reg
    def _adapter(self,adapter_registration_id):
        raw=self.store.phase6_get('adapter_registrations','adapter_registration_id',adapter_registration_id)
        if raw is None or raw['status']!='current':raise AdapterUnregistered('adapter_unregistered')
        raw['supported_semantic_controls']=tuple(raw['supported_semantic_controls']); raw.setdefault('vendor_command_mapping',dict(raw.get('command_mapping') or {})); return AdapterRegistration(**raw)
    def issue_control_request(self,*,assessment_id,active_execution_id,owner_id,owner_fence,requested_control,target_handle,created_at):
        if requested_control not in self.SEMANTIC_CONTROLS:raise ValueError('unsupported semantic control')
        if not self._valid_target_handle(target_handle): raise TargetScopeViolation('target_scope_violation')
        if self.store.continuation_reconciliation_required(active_execution_id): raise ConcurrencyConflict('continuation_reconciliation_required')
        owner=self._owner(active_execution_id,owner_id,owner_fence,at_time=created_at)
        assessment=self.continuation.get_assessment(assessment_id)
        if assessment is None or assessment.active_execution_id!=active_execution_id:raise ValueError('authoritative committed continuation assessment required')
        if requested_control not in self.POSTURE_ALLOWED_CONTROLS.get(assessment.continuation_posture,frozenset()):raise ValueError('control_not_permitted_by_continuation_posture')
        snap=self.dependencies.get_snapshot(assessment.committed_snapshot_id)
        if snap is None:raise ConcurrencyConflict('snapshot_conflict: committed snapshot unavailable')
        self.dependencies.validate_snapshot(snap); rec=self.store.get_active_execution(active_execution_id)
        if rec is None:raise KeyError('active execution not found')
        if self.bridge is None: raise ConcurrencyConflict('canonical_state_unavailable: live bridge required for consequential control')
        canonical_step=self.bridge.episode_step(rec.episode_id)
        if assessment.canonical_step is None or assessment.canonical_step!=canonical_step: raise ConcurrencyConflict('stale_continuation_assessment: canonical step changed')
        trusted_created_at=self.store.now().isoformat()
        req=ExecutionControlRequest(SemanticId.new('ctrl').value,active_execution_id,rec.execution_id,rec.attempt,owner.owner_id,owner.owner_fence,snap.governance_snapshot_id,assessment_id,requested_control,target_handle,rec.configuration_id,created_at,trusted_created_at)
        self.store.phase6_put('control_requests','control_request_id',req.control_request_id,asdict(req),{'active_execution_id':active_execution_id})
        self.store.record_supervisory_operation('control_requested',occurred_at=created_at,configuration_id=rec.configuration_id,subject_id=active_execution_id,payload={'initiating_event_id':assessment_id,'operation':'issue_control_request','state_version_before':snap.descriptor_version,'authority_source':f'{owner.owner_id}:{owner.owner_fence}','result_ref':req.control_request_id,'invariant_status':'authorized','caller_created_at':created_at,'trusted_created_at':trusted_created_at,'error':None}); return req
    def dispatch_control_request(self,*,control_request_id,adapter_registration_id,owner_id,owner_fence,target_handle,control_region_at_request,capability_evidence_ref,mapping_identity,dispatched_at,dispatch_result='dispatched'):
        raw=self.store.phase6_get('control_requests','control_request_id',control_request_id)
        if raw is None:raise KeyError('control request not found')
        req=ExecutionControlRequest(**raw)
        if self.store.continuation_reconciliation_required(req.active_execution_id): raise ConcurrencyConflict('continuation_reconciliation_required')
        self._owner(req.active_execution_id,owner_id,owner_fence,at_time=dispatched_at)
        assessment=self.continuation.get_assessment(req.continuation_assessment_id)
        rec=self.store.get_active_execution(req.active_execution_id)
        if assessment is None or rec is None: raise ConcurrencyConflict('stale_continuation_assessment')
        if self.bridge is None: raise ConcurrencyConflict('canonical_state_unavailable: live bridge required for consequential control')
        canonical_step=self.bridge.episode_step(rec.episode_id)
        if assessment.canonical_step is None or assessment.canonical_step!=canonical_step: raise ConcurrencyConflict('stale_continuation_assessment: canonical step changed')
        snap=self.dependencies.get_snapshot(req.governance_snapshot_id)
        if snap is None:raise ConcurrencyConflict('snapshot_conflict')
        self.dependencies.validate_snapshot(snap); reg=self._adapter(adapter_registration_id)
        if reg.configuration_id!=req.configuration_id:raise AdapterUnregistered('adapter_unregistered: configuration mismatch')
        if req.requested_control not in reg.supported_semantic_controls:raise AdapterUnregistered('adapter_unregistered: unsupported semantic control')
        suffix=target_handle[len(reg.target_handle_namespace):] if target_handle.startswith(reg.target_handle_namespace) else ''
        if target_handle!=req.target_handle or not self._valid_target_suffix(suffix):raise TargetScopeViolation('target_scope_violation')
        mapped_semantic=reg.command_mapping[req.requested_control]
        if mapped_semantic not in self.SEMANTIC_CONTROLS or self.CONTROL_ORDER[mapped_semantic]>self.CONTROL_ORDER[req.requested_control]:raise ControlMappingWidened('control_mapping_widened')
        vendor_command=reg.vendor_command_mapping[req.requested_control]
        trusted_dispatched_at=self.store.now().isoformat()
        attempt=ControlAttemptRecord(SemanticId.new('cattempt').value,control_request_id,reg.adapter_registration_id,reg.version,target_handle,req.requested_control,vendor_command,control_region_at_request,capability_evidence_ref,mapping_identity,dispatched_at,dispatch_result,owner_id,owner_fence,trusted_dispatched_at)
        self.store.phase6_put('control_attempts','control_attempt_id',attempt.control_attempt_id,asdict(attempt),{'control_request_id':control_request_id})
        self.store.record_supervisory_operation('control_dispatched',occurred_at=dispatched_at,configuration_id=req.configuration_id,subject_id=req.active_execution_id,payload={'initiating_event_id':control_request_id,'operation':'dispatch_control_request','authority_source':f'{owner_id}:{owner_fence}','result_ref':attempt.control_attempt_id,'invariant_status':'exact_mapping','caller_dispatched_at':dispatched_at,'trusted_dispatched_at':trusted_dispatched_at,'error':None}); return attempt
    def record_enforcement_outcome(self,*,control_attempt_id,outcome,controller_evidence_ref,observed_control_region,recorded_at,attestation_evidence=None,attestation_verified=None):
        if outcome not in self.OUTCOMES:raise ValueError('unsupported enforcement outcome')
        raw=self.store.phase6_get('control_attempts','control_attempt_id',control_attempt_id)
        if raw is None:raise KeyError('control attempt not found')
        attempt=ControlAttemptRecord(**raw); reg=self._adapter(attempt.adapter_registration_id); verified=self.store.trust.verify_controller_attestation(adapter_registration=reg,control_attempt=attempt,outcome=outcome,controller_evidence_ref=controller_evidence_ref,attestation_evidence=attestation_evidence); status='verified' if verified else ('weak' if reg.controller_attestation_method=='none' else 'unverified')
        rec=EnforcementRecord(SemanticId.new('enf').value,attempt.control_request_id,control_attempt_id,reg.adapter_registration_id,outcome,status,controller_evidence_ref,observed_control_region,recorded_at,attempt.owner_fence)
        self.store.phase6_put('enforcement_records','enforcement_record_id',rec.enforcement_record_id,asdict(rec),{'control_attempt_id':control_attempt_id}); reqraw=self.store.phase6_get('control_requests','control_request_id',attempt.control_request_id)
        self.store.record_supervisory_operation('enforcement_recorded',occurred_at=recorded_at,configuration_id=reqraw.get('configuration_id') if reqraw else None,subject_id=reqraw.get('active_execution_id') if reqraw else None,payload={'initiating_event_id':control_attempt_id,'operation':'record_enforcement_outcome','authority_source':reg.adapter_registration_id,'result_ref':rec.enforcement_record_id,'invariant_status':status,'enforcement_outcome':outcome,'error':None}); return rec
    def fence_execution_authority(self,*,active_execution_id,owner_id,owner_fence,reason):
        self._owner(active_execution_id,owner_id,owner_fence); rec=self.store.get_active_execution(active_execution_id)
        if rec is None:raise KeyError('active execution not found')
        return tuple(self.bridge.runtime.invalidate_native_execution_authorizations(episode_id=rec.episode_id,reason=reason))
