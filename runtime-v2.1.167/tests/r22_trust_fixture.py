from datetime import datetime, timezone
from pvpp_runtime.supervision import HostTrustProvider, SQLiteSupervisoryStore

_PROOFS={
    'admin':'proof-admin',
    'test-admin':'proof-test-admin',
    'model':'proof-model',
    'test':'proof-test',
}

def proof(authority):
    return _PROOFS[authority]

def test_trust_provider(clock=None):
    roots={
        'admin':{'proof':_PROOFS['admin'],'roles':('*',),'configurations':('*',)},
        'test-admin':{'proof':_PROOFS['test-admin'],'roles':('*',),'configurations':('*',)},
        'model':{'proof':_PROOFS['model'],'roles':('dependency_registration',),'configurations':('*',)},
        'test':{'proof':_PROOFS['test'],'roles':('*',),'configurations':('*',)},
    }
    def controller_verifier(**kw):
        return kw.get('attestation_evidence')=='signed:controller'
    def layer1_verifier(**kw):
        return kw.get('authority_evidence')=='signed:layer1'
    return HostTrustProvider(
        roots,
        controller_attestation_verifier=controller_verifier,
        layer1_authority_verifier=layer1_verifier,
        clock=clock or (lambda: datetime(2026,10,2,12,0,0,tzinfo=timezone.utc)),
    )

def trusted_store(path, *, clock=None):
    return SQLiteSupervisoryStore(path, trust_provider=test_trust_provider(clock=clock))

def register_source(obs, source):
    obs.register_source(source, authority_proof=proof(source.registration_authority))
