"""Tests for ``parsed/__init__.py``, the package root.

Pins that the version it stamps agrees with ``pyproject.toml``'s, that it re-exports seared's declaration surface as
seared's own objects (the base class and the decorator renamed), that no field type or error of seared's is missed,
and that every class it exports has annotations ``typing.get_type_hints`` can resolve.
"""

from __future__ import annotations

import inspect
import tomllib
import typing
from pathlib import Path

import pytest
import seared

import parsed

_ROOT = Path(__file__).parent.parent

_RENAMED = {'Parsed': 'Seared', 'parsed': 'seared'}


def test_the_version_is_stamped_the_same_in_both_places():
    project = tomllib.loads((_ROOT / 'pyproject.toml').read_text())
    # The release workflow tags from one and refuses to run if they differ;
    # consumers read the other. Failing here catches it before the merge.
    assert project['project']['version'] == parsed.__version__


@pytest.mark.parametrize(('name', 'original'), sorted(_RENAMED.items()))
def test_the_base_and_the_decorator_are_seared_s_renamed(name, original):
    assert getattr(parsed, name) is getattr(seared, original)


# seared's names, as parsed exports them; parsed's own (`Command`, `Effect`, …) aren't re-exports.
_REEXPORTED = sorted(set(parsed.__all__) & set(seared.__all__) - {'__version__'})


@pytest.mark.parametrize('name', _REEXPORTED)
def test_every_re_export_is_seared_s_own_object(name):
    assert getattr(parsed, name) is getattr(seared, name)


def test_every_field_type_and_error_of_seared_s_is_re_exported():
    # A field type seared adds later fails here until it's re-exported. `Field`
    # itself, the base a custom field subclasses, stays seared's, as in zeared.
    # `NDArray`, `PandasFrame` and `PolarsFrame` are stand-ins of their own
    # when their extra is missing, so they don't count here; the identity test
    # above covers them.
    wanted = {
        name
        for name in seared.__all__
        if inspect.isclass(obj := getattr(seared, name))
        and obj is not seared.Field
        and (issubclass(obj, seared.Field) or issubclass(obj, seared.SearedError))
    }
    assert wanted <= set(parsed.__all__)


_CLASSES = sorted(name for name in parsed.__all__ if inspect.isclass(getattr(parsed, name)))


@pytest.mark.parametrize('name', _CLASSES)
def test_every_exported_classs_annotations_resolve(name):
    # As zeared pins it: an annotation naming a type imported only for type
    # checking, here or in seared, makes `get_type_hints` raise `NameError`.
    typing.get_type_hints(getattr(parsed, name))
