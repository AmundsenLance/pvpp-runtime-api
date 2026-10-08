from dataclasses import replace
import pytest
from pvpp_runtime import ExecutionLicenseEnvelope, ExecutionEpisode
from test_v2_authority_bound_callthrough_v0130 import setup, auth, action


def test_v0131_canonical_license_fabrication_rejected_at_epsilon():
    rt,br,ep=setup()
    fake=replace(ep.license)
    assert fake == ep.license and fake is not ep.license
    with pytest.raises(ValueError, match="runtime-recognized current canonical execution license"):
        rt.instantiate_execution("fake-license-episode", fake, entry_sufficient=True, max_steps=1)


def test_v0131_episode_fabrication_cannot_mint_native_authority():
    rt,br,ep=setup()
    fake=ExecutionEpisode("fabricated",ep.license,1,entry_sufficient=True,active=True)
    with pytest.raises(ValueError, match="runtime-issued canonical execution episode"):
        rt.issue_native_execution_authorization(fake,action(ep),br,decision_cycle_id="fake-cycle")


def test_v0131_reconstructed_genuine_episode_is_non_authorizing():
    rt,br,ep=setup()
    copied=replace(ep)
    assert copied == ep and copied is not ep
    with pytest.raises(ValueError, match="runtime-issued canonical execution episode"):
        rt.issue_native_execution_authorization(copied,action(ep),br,decision_cycle_id="copy-cycle")


def test_v0131_legitimate_canonical_lineage_executes_once():
    calls=[]
    rt,br,ep=setup(lambda c: calls.append(c.execution_id) or "ok")
    a=auth(rt,br,ep)
    result=rt.invoke_authorized_native(a,br)
    assert result.status == "succeeded"
    assert len(calls) == 1


def test_v0131_lineage_invalidation_retires_episode_before_new_authorization():
    calls=[]
    rt,br,ep=setup(lambda c: calls.append(1))
    first=auth(rt,br,ep)
    rt.invalidate_native_execution_authorizations(episode_id=ep.episode_id,reason="governance re-entry")
    with pytest.raises(RuntimeError, match="invalidated"):
        rt.invoke_authorized_native(first,br)
    with pytest.raises(ValueError, match="runtime-issued canonical execution episode"):
        auth(rt,br,ep,attempt=2)
    assert calls == []
