from dvc.utils.diff import diff as _diff
from dvc.utils.diff import format_dict

from .show import NoParamsError


def _get_params(repo, *args, revs=None, **kwargs):
    try:
        params = repo.params.show(*args, **kwargs, revs=revs)
        return params
    except NoParamsError:
        return {}


def diff(repo, *args, a_rev=None, b_rev=None, **kwargs):
    if repo.scm.no_commits:
        return {}

    with_unchanged = kwargs.pop("all", False)

    a_rev = a_rev or "HEAD"
    b_rev = b_rev or "workspace"

    params = _get_params(repo, *args, **kwargs, revs=[a_rev, b_rev])
    old = params.get(a_rev, {})
    new = params.get(b_rev, {})

    return _diff(
        format_dict(old), format_dict(new), with_unchanged=with_unchanged
    )
