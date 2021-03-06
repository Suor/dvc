import logging

import pytest
from funcy import first

from dvc.exceptions import DvcException
from dvc.repo.experiments import Experiments, MultipleBranchError
from dvc.repo.experiments.base import EXEC_APPLY, EXEC_CHECKPOINT


@pytest.mark.parametrize("workspace", [True, False])
def test_new_checkpoint(
    tmp_dir, scm, dvc, checkpoint_stage, mocker, workspace
):
    new_mock = mocker.spy(dvc.experiments, "new")
    results = dvc.experiments.run(
        checkpoint_stage.addressing, params=["foo=2"], tmp_dir=not workspace
    )
    exp = first(results)

    new_mock.assert_called_once()
    for rev in dvc.brancher([exp]):
        if rev == "workspace":
            continue
        tree = dvc.repo_tree
        with tree.open(tmp_dir / "foo") as fobj:
            assert fobj.read().strip() == "5"
        with tree.open(tmp_dir / "metrics.yaml") as fobj:
            assert fobj.read().strip() == "foo: 2"

    if workspace:
        assert scm.get_ref(EXEC_APPLY) == exp
    assert scm.get_ref(EXEC_CHECKPOINT) == exp
    if workspace:
        assert (tmp_dir / "foo").read_text().strip() == "5"
        assert (tmp_dir / "metrics.yaml").read_text().strip() == "foo: 2"


@pytest.mark.parametrize(
    "checkpoint_resume, workspace",
    [
        (Experiments.LAST_CHECKPOINT, True),
        (Experiments.LAST_CHECKPOINT, False),
        ("foo", True),
        ("foo", False),
    ],
)
def test_resume_checkpoint(
    tmp_dir, scm, dvc, checkpoint_stage, checkpoint_resume, workspace
):
    with pytest.raises(DvcException):
        dvc.experiments.run(
            checkpoint_stage=checkpoint_stage.addressing,
            checkpoint_resume=checkpoint_resume,
            tmp_dir=not workspace,
        )

    results = dvc.experiments.run(
        checkpoint_stage.addressing, params=["foo=2"], tmp_dir=not workspace
    )

    with pytest.raises(DvcException):
        dvc.experiments.run(
            checkpoint_stage.addressing,
            checkpoint_resume="abc1234",
            tmp_dir=not workspace,
        )

    if checkpoint_resume != Experiments.LAST_CHECKPOINT:
        checkpoint_resume = first(results)

    if not workspace:
        dvc.experiments.apply(first(results))
    results = dvc.experiments.run(
        checkpoint_stage.addressing,
        checkpoint_resume=checkpoint_resume,
        tmp_dir=not workspace,
    )
    exp = first(results)

    for rev in dvc.brancher([exp]):
        if rev == "workspace":
            continue
        tree = dvc.repo_tree
        with tree.open(tmp_dir / "foo") as fobj:
            assert fobj.read().strip() == "10"
        with tree.open(tmp_dir / "metrics.yaml") as fobj:
            assert fobj.read().strip() == "foo: 2"

    if workspace:
        assert scm.get_ref(EXEC_APPLY) == exp
    assert scm.get_ref(EXEC_CHECKPOINT) == exp


@pytest.mark.parametrize("workspace", [True, False])
def test_reset_checkpoint(
    tmp_dir, scm, dvc, checkpoint_stage, caplog, workspace
):
    from dvc.repo.experiments.base import CheckpointExistsError

    dvc.experiments.run(
        checkpoint_stage.addressing, name="foo", tmp_dir=not workspace,
    )

    if workspace:
        scm.reset(hard=True)
        scm.gitpython.repo.git.clean(force=True)

    if workspace:
        with caplog.at_level(logging.ERROR):
            dvc.experiments.run(
                checkpoint_stage.addressing,
                name="foo",
                params=["foo=2"],
                tmp_dir=not workspace,
            )
        assert "checkpoint experiment conflicts with existing" in caplog.text

        scm.reset(hard=True)
        scm.gitpython.repo.git.clean(force=True)
    else:
        with pytest.raises(CheckpointExistsError):
            dvc.experiments.run(
                checkpoint_stage.addressing,
                name="foo",
                params=["foo=2"],
                tmp_dir=not workspace,
            )

    results = dvc.experiments.run(
        checkpoint_stage.addressing,
        params=["foo=2"],
        name="foo",
        force=True,
        tmp_dir=not workspace,
    )
    exp = first(results)

    for rev in dvc.brancher([exp]):
        if rev == "workspace":
            continue
        tree = dvc.repo_tree
        with tree.open(tmp_dir / "foo") as fobj:
            assert fobj.read().strip() == "5"
        with tree.open(tmp_dir / "metrics.yaml") as fobj:
            assert fobj.read().strip() == "foo: 2"

    if workspace:
        assert scm.get_ref(EXEC_APPLY) == exp
    assert scm.get_ref(EXEC_CHECKPOINT) == exp


@pytest.mark.parametrize("workspace", [True, False])
def test_resume_branch(tmp_dir, scm, dvc, checkpoint_stage, workspace):
    results = dvc.experiments.run(
        checkpoint_stage.addressing, params=["foo=2"], tmp_dir=not workspace
    )
    branch_rev = first(results)
    if not workspace:
        dvc.experiments.apply(branch_rev)

    results = dvc.experiments.run(
        checkpoint_stage.addressing,
        checkpoint_resume=branch_rev,
        tmp_dir=not workspace,
    )
    checkpoint_a = first(results)
    if not workspace:
        dvc.experiments.apply(checkpoint_a, force=True)

    with pytest.raises(DvcException):
        results = dvc.experiments.run(
            checkpoint_stage.addressing,
            checkpoint_resume=branch_rev,
            params=["foo=100"],
            tmp_dir=not workspace,
        )

    dvc.experiments.apply(branch_rev, force=True)
    results = dvc.experiments.run(
        checkpoint_stage.addressing,
        checkpoint_resume=branch_rev,
        params=["foo=100"],
        tmp_dir=not workspace,
    )
    checkpoint_b = first(results)

    for rev in dvc.brancher([checkpoint_a]):
        if rev == "workspace":
            continue
        tree = dvc.repo_tree
        with tree.open(tmp_dir / "foo") as fobj:
            assert fobj.read().strip() == "10"
        with tree.open(tmp_dir / "metrics.yaml") as fobj:
            assert fobj.read().strip() == "foo: 2"

    for rev in dvc.brancher([checkpoint_b]):
        if rev == "workspace":
            continue
        tree = dvc.repo_tree
        with tree.open(tmp_dir / "foo") as fobj:
            assert fobj.read().strip() == "10"
        with tree.open(tmp_dir / "metrics.yaml") as fobj:
            assert fobj.read().strip() == "foo: 100"

    with pytest.raises(MultipleBranchError):
        dvc.experiments.get_branch_by_rev(branch_rev)

    assert branch_rev == dvc.experiments.scm.gitpython.repo.git.merge_base(
        checkpoint_a, checkpoint_b
    )
