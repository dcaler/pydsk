"""Test that all modules scaffold correctly (catches __init__.py typos)."""

import pytest


def test_main_package_imports():
    """Verify the main dsk package imports without error."""
    import dsk
    assert dsk is not None


def test_subpackage_imports():
    """Verify all subpackages import without error."""
    import dsk.agents
    import dsk.sectors
    import dsk.parameters
    import dsk.innovation
    import dsk.io
    import dsk.markets
    import dsk.policy
    import dsk.climate
    import dsk.trade
    import dsk.accounting

    # Basic sanity check that modules are truthy
    assert dsk.agents is not None
    assert dsk.sectors is not None
    assert dsk.parameters is not None
    assert dsk.innovation is not None
    assert dsk.io is not None
    assert dsk.markets is not None
    assert dsk.policy is not None
    assert dsk.climate is not None
    assert dsk.trade is not None
    assert dsk.accounting is not None
